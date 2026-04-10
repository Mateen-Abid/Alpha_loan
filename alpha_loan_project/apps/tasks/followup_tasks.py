"""Follow-up Tasks - Scheduled follow-up messaging and inbound AI handling."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
import logging
import re
from typing import Dict, Optional

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.ai.services.ai_orchestrator import AIOrchestrator
from apps.collections.models import CollectionCase, InteractionLedger, PaymentCommitment
from apps.collections.services.collection_service import CollectionService
from apps.collections.workflows.state_machine import WorkflowStateMachine
from apps.collections.workflows.workflow_states import WorkflowActions, WorkflowState
from apps.communications.services.communication_router import CommunicationRouter, ExternalDispatchError

logger = logging.getLogger(__name__)

_KV_PATTERN = re.compile(r"([a-zA-Z0-9_]+)=([^;\n]+)")
_LEGAL_KEYWORDS = ("bankruptcy", "lawyer", "attorney", "wrong person", "identity", "identity theft")
_REFUSAL_KEYWORDS = ("no", "can't", "cannot", "wont", "won't", "not paying", "refuse")
_AGREEMENT_KEYWORDS = ("ok", "okay", "yes", "i can", "i will", "send today", "agree", "done")
_STOP_PAYMENT_CODES = {"STOP_PMT", "PAYMENT_STOPPED_RECALLED"}
_CLOSED_ACCOUNT_CODES = {"CLOSED_ACC", "REASON_ACCOUNT_CLOSED"}
_FOLLOWUP_TONE_VARIANTS = (
    "Quick reminder",
    "Following up",
    "Action required",
    "Urgent reminder",
)
_REFERENCE_ESCALATION_PHRASES = (
    "contact your employer",
    "contact your references",
    "employer/references",
)
_CONTRACT_BREACH_PHRASES = (
    "contract obligation",
    "contract breach",
)
_AUTOMATION_MODES = {"all", "allowlist", "off"}
_DEFAULT_PROPOSAL_WINDOW_HOURS = 24
_DEFAULT_FOLLOWUP_INTERVAL_HOURS = 1
_DEFAULT_MAX_WAVE_LEVEL = 5


def _trim_text(value: str, max_chars: int = 180) -> str:
    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


def _safe_int(value: object, default: int = 0, min_value: Optional[int] = None, max_value: Optional[int] = None) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _parse_iso_datetime(raw: str) -> Optional[datetime]:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed
    except Exception:
        return None


def _get_followup_interval_hours() -> int:
    return _safe_int(
        getattr(settings, "COLLECTION_FOLLOWUP_INTERVAL_HOURS", _DEFAULT_FOLLOWUP_INTERVAL_HOURS),
        default=_DEFAULT_FOLLOWUP_INTERVAL_HOURS,
        min_value=1,
    )


def _get_proposal_window_hours() -> int:
    return _safe_int(
        getattr(settings, "COLLECTION_PROPOSAL_WINDOW_HOURS", _DEFAULT_PROPOSAL_WINDOW_HOURS),
        default=_DEFAULT_PROPOSAL_WINDOW_HOURS,
        min_value=1,
    )


def _get_max_wave_level() -> int:
    return _safe_int(
        getattr(settings, "COLLECTION_MAX_WAVE_LEVEL", _DEFAULT_MAX_WAVE_LEVEL),
        default=_DEFAULT_MAX_WAVE_LEVEL,
        min_value=1,
    )


def _parse_allowed_row_ids(raw: object) -> set[int]:
    if raw is None:
        return set()
    if isinstance(raw, str):
        candidates = [item.strip() for item in raw.split(",")]
    elif isinstance(raw, (list, tuple, set)):
        candidates = list(raw)
    else:
        candidates = [raw]

    allowed: set[int] = set()
    for item in candidates:
        if item in (None, "", "null"):
            continue
        try:
            allowed.add(int(str(item).strip()))
        except Exception:
            continue
    return allowed


def _automation_mode() -> str:
    mode = str(getattr(settings, "AUTO_REPLY_MODE", "all") or "all").strip().lower()
    return mode if mode in _AUTOMATION_MODES else "all"


def _case_row_id_int(case: CollectionCase) -> Optional[int]:
    raw = case.partner_row_id or case.account_id
    if raw in (None, "", "null"):
        return None
    try:
        return int(str(raw).strip())
    except Exception:
        return None


def _is_case_allowed_for_automation(case: CollectionCase) -> bool:
    mode = _automation_mode()
    if mode == "off":
        return False
    if mode != "allowlist":
        return True

    allowed = _parse_allowed_row_ids(getattr(settings, "AUTO_REPLY_ALLOWED_ROW_IDS", ""))
    if not allowed:
        return False
    row_id = _case_row_id_int(case)
    return row_id is not None and row_id in allowed


def _proposal_deadline(now: datetime) -> datetime:
    return now + timedelta(hours=_get_proposal_window_hours())


def _resolve_proposal_deadline(meta: Dict[str, str], now: datetime) -> datetime:
    parsed = _parse_iso_datetime(meta.get("proposal_deadline_at", ""))
    return parsed or _proposal_deadline(now)


def _current_wave_level(meta: Dict[str, str]) -> int:
    return _safe_int(meta.get("wave_level", "1"), default=1, min_value=1, max_value=_get_max_wave_level())


def _build_conversation_memory(case: CollectionCase) -> str:
    max_messages = max(1, int(getattr(settings, "COLLECTION_MEMORY_MAX_MESSAGES", 8)))
    interactions = (
        InteractionLedger.objects.filter(collection_case=case)
        .order_by("-created_at")
        .only("interaction_type", "channel", "message_content")
    )[:max_messages]

    if not interactions:
        return "No previous interaction history."

    lines = []
    for item in reversed(list(interactions)):
        role = "Borrower" if item.interaction_type == InteractionLedger.InteractionType.INBOUND else "Agent"
        lines.append(f"{role} ({item.channel}): {_trim_text(item.message_content, 160)}")
    return "\n".join(lines)


def _build_prior_loan_history(case: CollectionCase) -> str:
    max_cases = max(1, int(getattr(settings, "COLLECTION_HISTORY_MAX_CASES", 5)))
    matcher: Q | None = None
    if case.borrower_phone:
        matcher = Q(borrower_phone=case.borrower_phone)
    if case.borrower_email:
        email_query = Q(borrower_email=case.borrower_email)
        matcher = email_query if matcher is None else (matcher | email_query)
    if matcher is None:
        return "No prior loan match identifiers."

    previous_cases = (
        CollectionCase.objects.filter(matcher)
        .exclude(id=case.id)
        .order_by("-created_at")
        .only("account_id", "status", "amount_paid", "total_due", "delinquent_date")
    )[:max_cases]

    if not previous_cases:
        return "No prior loan history found."

    history_lines = []
    for prev in previous_cases:
        paid_ratio = "unknown"
        try:
            if prev.total_due and prev.total_due > 0:
                ratio = (prev.amount_paid / prev.total_due) * Decimal("100")
                paid_ratio = f"{ratio:.0f}% paid"
        except Exception:
            paid_ratio = "unknown"
        history_lines.append(
            f"Account {prev.account_id}: status={prev.status}, total_due=${prev.total_due:.2f}, "
            f"paid=${prev.amount_paid:.2f}, {paid_ratio}, delinquent_date={prev.delinquent_date}"
        )
    return "\n".join(history_lines)


def _policy_flags() -> Dict[str, bool]:
    return {
        "allow_contract_breach_language": bool(
            getattr(settings, "COLLECTION_POLICY_ENABLE_CONTRACT_BREACH_LANGUAGE", True)
        ),
        "allow_reference_escalation": bool(
            getattr(settings, "COLLECTION_POLICY_ENABLE_REFERENCE_ESCALATION", False)
        ),
    }


def _apply_risk_policy(message: str) -> str:
    policy = _policy_flags()
    cleaned = message or ""

    if not policy["allow_contract_breach_language"]:
        for phrase in _CONTRACT_BREACH_PHRASES:
            cleaned = re.sub(phrase, "account follow-up", cleaned, flags=re.IGNORECASE)
    if not policy["allow_reference_escalation"]:
        for phrase in _REFERENCE_ESCALATION_PHRASES:
            cleaned = re.sub(phrase, "alternative contact process", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _build_case_context(case: CollectionCase) -> Dict[str, object]:
    meta = _extract_meta(case)
    proposal_level = int(meta.get("proposal_level", "1")) if meta.get("proposal_level", "1").isdigit() else 1
    no_reply_count = int(meta.get("no_reply_count", "0")) if meta.get("no_reply_count", "0").isdigit() else 0
    wave_level = _current_wave_level(meta)
    reason_code = meta.get("ingest_reason_code", "")
    nsf_count_text = (meta.get("raw_reason", "") + " " + (meta.get("raw_comment", ""))).lower()
    nsf_band = "1_2_nsf"
    if "3rd" in nsf_count_text or "4nsf" in nsf_count_text or "5nsf" in nsf_count_text or "6nsf" in nsf_count_text:
        nsf_band = "3_plus_nsf"

    return {
        "total_due": case.total_due,
        "current_workflow_step": case.current_workflow_step,
        "days_delinquent": case.get_age_in_days(),
        "borrower_name": case.borrower_name,
        "reason_code": reason_code,
        "proposal_level": proposal_level,
        "wave_level": wave_level,
        "no_reply_count": no_reply_count,
        "nsf_band": nsf_band,
        "conversation_memory": _build_conversation_memory(case),
        "prior_loan_history": _build_prior_loan_history(case),
        "policy_flags": _policy_flags(),
    }


def _build_dispatch_payload(
    case: CollectionCase,
    message: str,
    *,
    subject: str,
    ai_generated: bool,
) -> Dict[str, object]:
    return {
        "row_id": case.partner_row_id or case.account_id,
        "case_id": case.id,
        "phone": case.borrower_phone,
        "email": case.borrower_email,
        "message": message,
        "subject": subject,
        "ai_generated": ai_generated,
    }


def _select_outbound_channel(case: CollectionCase) -> str:
    return "sms" if case.borrower_phone else "email"


def _is_daily_reject_case(case: CollectionCase) -> bool:
    notes = (case.notes or "").lower()
    return "board_id=70" in notes and "group_id=91" in notes


def _extract_meta(case: CollectionCase) -> Dict[str, str]:
    values: Dict[str, str] = {}
    for key, value in _KV_PATTERN.findall(case.notes or ""):
        values[key] = value.strip()
    return values


def _append_case_meta(case: CollectionCase, updates: Dict[str, object]) -> None:
    items = [f"{k}={v}" for k, v in updates.items()]
    line = "; ".join(items)
    case.notes = f"{case.notes}\n{line}".strip() if case.notes else line


def _proposal_level_to_step(level: int) -> str:
    if level <= 3:
        return CollectionCase.WorkflowStep.STEP_1
    if level <= 6:
        return CollectionCase.WorkflowStep.STEP_2
    if level <= 10:
        return CollectionCase.WorkflowStep.STEP_3
    if level <= 13:
        return CollectionCase.WorkflowStep.STEP_4
    return CollectionCase.WorkflowStep.FINAL_PRESSURE


def _safe_decimal(value: str, default: Decimal) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return default


def _daily_reject_financials(case: CollectionCase) -> Dict[str, Decimal]:
    meta = _extract_meta(case)
    missed = _safe_decimal(meta.get("last_missed_due", "0"), case.principal_amount or Decimal("0"))
    fee = Decimal("50.00")
    immediate = missed + fee
    balance = _safe_decimal(meta.get("balance_amount", "0"), case.total_due or Decimal("0"))
    return {"missed": missed, "fee": fee, "immediate": immediate, "balance": balance}


def _build_daily_reject_offer(
    case: CollectionCase,
    level: int,
    *,
    wave_level: int,
    no_reply_count: int = 0,
) -> str:
    meta = _extract_meta(case)
    reason_code = meta.get("ingest_reason_code", "")
    amounts = _daily_reject_financials(case)
    immediate_text = f"${amounts['immediate']:.2f}"
    missed_text = f"${amounts['missed']:.2f}"

    offer_lines = {
        1: f"Please send {immediate_text} by Interac now.",
        2: f"Please send {immediate_text} by Interac by end of day.",
        3: f"Please send {immediate_text} by Interac by end of week.",
        4: f"Please send {missed_text} by Interac now; we will add the $50.00 NSF fee to your next payment.",
        5: (
            f"Please send {missed_text} by Interac now; we will split the $50.00 NSF fee "
            "across your next 2 payments ($25.00 + $25.00)."
        ),
        6: "Please send the $50.00 NSF fee by Interac now; we will duplicate your next payment.",
        7: "Please send the $50.00 NSF fee by Interac now; we will move the missed payment to the end of your loan.",
        8: (
            "Please send the $50.00 NSF fee by Interac now; we will add the missed payment amount "
            "across your next 2 payments."
        ),
        9: "No Interac payment now; we will add the missed payment and NSF fee to your next payment.",
        10: (
            "No Interac payment now; we will add the missed payment to your next payment and move "
            "the NSF fee to the end of your loan."
        ),
        11: (
            "No Interac payment now; we will split the missed payment across your next 2 payments "
            "and move the NSF fee to the end of your loan."
        ),
        12: (
            "No Interac payment now; we will add the NSF fee to your next payment and move the missed "
            "payment to the end of your loan."
        ),
        13: (
            "No Interac payment now; we will split the NSF fee across your next 2 payments and move the "
            "missed payment to the end of your loan."
        ),
        14: (
            "No Interac payment now; resume regular payments and we will add the missed payment and NSF fee "
            "as regular payments at the end of your schedule."
        ),
    }
    offer = offer_lines.get(level, offer_lines[14])

    if reason_code in _CLOSED_ACCOUNT_CODES:
        payment_instruction_suffix = " Please send your updated void cheque/PAD details so scheduled payments can resume."
    else:
        payment_instruction_suffix = (
            " Please call your bank to remove the stop payment so your next scheduled payment can go through."
        )

    strict_suffix = ""
    policy = _policy_flags()
    if policy["allow_contract_breach_language"] and (no_reply_count >= 6 or level >= 12):
        strict_suffix = " This is a contract obligation and we need your response now."
    if policy["allow_reference_escalation"] and (no_reply_count >= 10 or level >= 14):
        strict_suffix = " If there is no response, we may contact your employer/references per contract terms."

    return (
        f"Your missed payment is ${amounts['missed']:.2f} and NSF fee is $50.00. "
        f"{offer}{payment_instruction_suffix}{strict_suffix}"
    ).strip()


def _classify_message_signal(message: str, ai_intent: str | None) -> str:
    text = (message or "").lower()
    if any(k in text for k in _LEGAL_KEYWORDS):
        return "legal_stop"
    if ai_intent == "refusal" or any(k in text for k in _REFUSAL_KEYWORDS):
        return "refusal"
    if ai_intent == "promise_to_pay" or any(k in text for k in _AGREEMENT_KEYWORDS):
        return "agreement"
    return "neutral"


@shared_task(bind=True, autoretry_for=(ExternalDispatchError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_followup_messages(self):
    """
    Send follow-up messages for active automation cases.
    For Daily Rejects, use deterministic proposal ladder logic.
    """
    cases = CollectionCase.objects.filter(
        automation_status=CollectionCase.AutomationStatus.ACTIVE,
        status=CollectionCase.CollectionStatus.ACTIVE,
        next_action_time__lte=timezone.now(),
    )

    orchestrator = AIOrchestrator()
    router = CommunicationRouter()
    followup_interval_hours = _get_followup_interval_hours()
    max_wave_level = _get_max_wave_level()

    for case in cases:
        try:
            if not _is_case_allowed_for_automation(case):
                logger.info("Skipping follow-up for case %s (row-id gate).", case.account_id)
                continue

            loop_now = timezone.now()
            is_daily = _is_daily_reject_case(case)
            channel = _select_outbound_channel(case)
            interaction_channel = (
                InteractionLedger.CommunicationChannel.SMS
                if channel == "sms"
                else InteractionLedger.CommunicationChannel.EMAIL
            )
            ai_generated = False
            meta = _extract_meta(case)
            level = _safe_int(meta.get("proposal_level", "1"), default=1, min_value=1, max_value=14)
            wave_level = _current_wave_level(meta)
            no_reply_seed = _safe_int(meta.get("no_reply_count", "0"), default=0, min_value=0)
            proposal_deadline_at = _resolve_proposal_deadline(meta, loop_now)
            proposal_escalated = False

            if is_daily:
                if loop_now >= proposal_deadline_at:
                    next_level = min(14, level + 1)
                    if next_level != level:
                        proposal_escalated = True
                    level = next_level
                    no_reply_seed = 0
                    proposal_deadline_at = _proposal_deadline(loop_now)
                no_reply_count = no_reply_seed + 1
                message = _apply_risk_policy(
                    _build_daily_reject_offer(
                        case,
                        level=level,
                        wave_level=wave_level,
                        no_reply_count=no_reply_count,
                    )
                )
            else:
                ai_message = orchestrator.generate_outbound_message(channel, _build_case_context(case))
                message = ai_message.get("message") or (
                    f"Reminder: Payment of ${case.get_remaining_balance():.2f} is due on your account."
                )
                message = _apply_risk_policy(message)
                ai_generated = bool(ai_message.get("status") == "success")
                no_reply_count = 0

            duplicate_exists = InteractionLedger.objects.filter(
                collection_case=case,
                interaction_type=InteractionLedger.InteractionType.OUTBOUND,
                channel=interaction_channel,
                message_content=message,
                created_at__gte=loop_now - timedelta(minutes=10),
            ).exists()
            if duplicate_exists:
                logger.info("Skipping duplicate follow-up dispatch for case %s", case.account_id)
                continue

            payload = _build_dispatch_payload(
                case,
                message,
                subject="Collection Reminder" if channel == "sms" else "Account Follow-up",
                ai_generated=ai_generated,
            )
            router.send_message(channel=channel, payload=payload)

            next_run = (
                loop_now + timedelta(hours=followup_interval_hours)
                if is_daily
                else loop_now + timedelta(days=3)
            )
            case.next_action_time = next_run
            case.next_followup_at = next_run
            case.last_contact_at = loop_now

            if is_daily:
                target_step = _proposal_level_to_step(level)
                if case.current_workflow_step != target_step:
                    case.current_workflow_step = target_step
                    case.workflow_step_started_at = loop_now
                next_wave_level = min(max_wave_level, wave_level + 1)
                if proposal_escalated:
                    case.workflow_step_started_at = loop_now
                _append_case_meta(
                    case,
                    {
                        "proposal_level": level,
                        "wave_level": next_wave_level,
                        "no_reply_count": no_reply_count,
                        "proposal_deadline_at": proposal_deadline_at.isoformat(),
                        "last_outreach_at": loop_now.isoformat(),
                    },
                )

            case.save()
            logger.info("Follow-up message sent for case %s", case.account_id)
        except Exception as exc:
            logger.error("Error sending follow-up for case %s: %s", case.account_id, str(exc))
            raise


@shared_task(bind=True, autoretry_for=(ExternalDispatchError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def process_borrower_message(self, case_id: int, interaction_id: int, message: str, channel: str = "sms"):
    """
    Process inbound borrower message with AI intent + response handling.
    Daily Rejects path uses deterministic progression rules.
    """
    try:
        case = CollectionCase.objects.get(id=case_id)
        interaction = InteractionLedger.objects.get(id=interaction_id)

        if interaction.ai_processed_at:
            logger.info("Skipping already-processed interaction_id=%s", interaction_id)
            return {"status": "success", "idempotent": True}

        orchestrator = AIOrchestrator()
        ai_result = orchestrator.process_borrower_message(message, _build_case_context(case), channel=channel)
        intent_data = ai_result.get("intent", {})
        intent = intent_data.get("intent")
        signal = _classify_message_signal(message, intent)

        interaction.ai_intent_detected = signal if signal != "neutral" else intent
        interaction.ai_sentiment_score = intent_data.get("confidence")
        interaction.ai_processed_at = timezone.now()
        interaction.status = InteractionLedger.InteractionStatus.REPLIED
        interaction.reply_message = ai_result.get("suggested_response", {}).get("message")
        interaction.save()

        now = timezone.now()
        followup_interval_hours = _get_followup_interval_hours()
        max_wave_level = _get_max_wave_level()
        automation_allowed = _is_case_allowed_for_automation(case)
        suggested_message = ""
        if _is_daily_reject_case(case):
            meta = _extract_meta(case)
            level = _safe_int(meta.get("proposal_level", "1"), default=1, min_value=1, max_value=14)
            wave_level = _current_wave_level(meta)
            proposal_deadline_at = _resolve_proposal_deadline(meta, now)

            if signal == "legal_stop":
                case.automation_status = CollectionCase.AutomationStatus.STOPPED
                _append_case_meta(case, {"automation_stop_reason": "legal_trigger"})
            elif signal == "refusal":
                level = min(14, level + 1)
                target_step = _proposal_level_to_step(level)
                case.current_workflow_step = target_step
                case.workflow_step_started_at = now
                proposal_deadline_at = _proposal_deadline(now)
                suggested_message = _apply_risk_policy(
                    _build_daily_reject_offer(case, level=level, wave_level=wave_level, no_reply_count=0)
                )
                _append_case_meta(
                    case,
                    {
                        "proposal_level": level,
                        "no_reply_count": 0,
                        "proposal_deadline_at": proposal_deadline_at.isoformat(),
                    },
                )
            elif signal == "agreement":
                promised_date = (now + timedelta(days=1)).date()
                exists = PaymentCommitment.objects.filter(
                    collection_case=case,
                    committed_amount=case.get_remaining_balance(),
                    promised_date=promised_date,
                    status__in=[
                        PaymentCommitment.CommitmentStatus.PENDING,
                        PaymentCommitment.CommitmentStatus.CONFIRMED,
                    ],
                ).exists()
                if not exists:
                    CollectionService.create_payment_commitment(
                        case=case,
                        committed_amount=case.get_remaining_balance(),
                        promised_date=promised_date,
                        payment_method="Interac",
                        commitment_source=channel.upper(),
                        notes="Created from borrower agreement in daily reject flow",
                    )
                case.automation_status = CollectionCase.AutomationStatus.PAUSED
                _append_case_meta(
                    case,
                    {
                        "no_reply_count": 0,
                        "proposal_level": level,
                        "proposal_deadline_at": proposal_deadline_at.isoformat(),
                        "promise_status": "pending",
                        "promise_date": promised_date.isoformat(),
                    },
                )
                suggested_message = _apply_risk_policy(
                    "Thanks for confirming. Please send payment as agreed today so we can close this item."
                )
            else:
                _append_case_meta(
                    case,
                    {
                        "no_reply_count": 0,
                        "proposal_level": level,
                        "proposal_deadline_at": proposal_deadline_at.isoformat(),
                    },
                )
                suggested_message = _apply_risk_policy(
                    _build_daily_reject_offer(case, level=level, wave_level=wave_level, no_reply_count=0)
                )
        else:
            if intent == "refusal":
                state_machine = WorkflowStateMachine(WorkflowState[case.current_workflow_step])
                if state_machine.transition(WorkflowActions.BORROWER_REFUSED):
                    case.current_workflow_step = state_machine.current_state.value
                    case.workflow_step_started_at = now
            elif intent == "promise_to_pay":
                promised_date = (now + timedelta(days=3)).date()
                exists = PaymentCommitment.objects.filter(
                    collection_case=case,
                    committed_amount=case.get_remaining_balance(),
                    promised_date=promised_date,
                    status__in=[
                        PaymentCommitment.CommitmentStatus.PENDING,
                        PaymentCommitment.CommitmentStatus.CONFIRMED,
                    ],
                ).exists()
                if not exists:
                    CollectionService.create_payment_commitment(
                        case=case,
                        committed_amount=case.get_remaining_balance(),
                        promised_date=promised_date,
                        payment_method="Unspecified",
                        commitment_source=channel.upper(),
                        notes="Auto-created from AI intent detection",
                    )
            suggested_message = _apply_risk_policy(ai_result.get("suggested_response", {}).get("message", ""))

        case.last_contact_at = now
        if _is_daily_reject_case(case):
            case.next_action_time = now + timedelta(hours=followup_interval_hours)
        else:
            case.next_action_time = now + timedelta(hours=2)
        case.next_followup_at = case.next_action_time
        case.save()

        should_send_now = bool(
            suggested_message
            and (
                case.automation_status == CollectionCase.AutomationStatus.ACTIVE
                or signal == "agreement"
            )
        )
        if should_send_now:
            if automation_allowed:
                router = CommunicationRouter()
                payload = _build_dispatch_payload(
                    case,
                    suggested_message,
                    subject="Account Update",
                    ai_generated=not _is_daily_reject_case(case),
                )
                outbound_channel = _select_outbound_channel(case)
                router.send_message(outbound_channel, payload)
                if _is_daily_reject_case(case):
                    meta_after_send = _extract_meta(case)
                    current_wave = _current_wave_level(meta_after_send)
                    _append_case_meta(
                        case,
                        {
                            "wave_level": min(max_wave_level, current_wave + 1),
                            "last_outreach_at": timezone.now().isoformat(),
                        },
                    )
                    case.save(update_fields=["notes", "updated_at"])
            else:
                logger.info("Skipping auto-reply dispatch for case %s (row-id gate).", case.account_id)

        logger.info("Processed message for case %s, signal: %s", case.account_id, signal)
        return {"status": "success", "intent": signal if signal != "neutral" else intent}
    except Exception as exc:
        logger.error("Error processing borrower message: %s", str(exc))
        raise


@shared_task(bind=True)
def process_borrowed_message(self, case_id: int, interaction_id: int, message: str):
    """Backward-compatible task alias."""
    return process_borrower_message.run(case_id=case_id, interaction_id=interaction_id, message=message, channel="sms")


@shared_task(bind=True, autoretry_for=(ExternalDispatchError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def process_voice_transcript(self, case_id: int, interaction_id: int, transcript: str):
    """Process voice call transcript"""
    try:
        case = CollectionCase.objects.get(id=case_id)
        interaction = InteractionLedger.objects.get(id=interaction_id)
        if interaction.ai_processed_at:
            return {"status": "success", "idempotent": True}

        process_borrower_message.run(case_id=case.id, interaction_id=interaction.id, message=transcript, channel="voice")
        logger.info("Processed voice transcript for case %s", case.account_id)
        return {"status": "success"}
    except Exception as exc:
        logger.error("Error processing voice transcript: %s", str(exc))
        raise
