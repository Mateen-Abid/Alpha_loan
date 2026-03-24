"""Follow-up Tasks - Scheduled follow-up messaging and inbound AI handling."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import logging
import re
from typing import Dict

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


def _trim_text(value: str, max_chars: int = 180) -> str:
    text = (value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3].rstrip() + "..."


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
    return {
        "total_due": case.total_due,
        "current_workflow_step": case.current_workflow_step,
        "days_delinquent": case.get_age_in_days(),
        "borrower_name": case.borrower_name,
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


def _build_daily_reject_offer(case: CollectionCase, level: int, no_reply_count: int = 0) -> str:
    first_name = (case.borrower_name or "there").split()[0]
    meta = _extract_meta(case)
    reason_code = meta.get("ingest_reason_code", "")
    amounts = _daily_reject_financials(case)
    immediate_text = f"${amounts['immediate']:.2f}"

    offer_lines = {
        1: f"send {immediate_text} by Interac now",
        2: f"send {immediate_text} by end of day",
        3: f"send {immediate_text} by end of week",
        4: f"send ${amounts['missed']:.2f} Interac now and we move fee to next payment",
        5: f"send ${amounts['missed']:.2f} Interac now and split fee over next 2 payments",
        6: f"send $50 fee Interac now and duplicate next payment",
        7: f"send $50 fee Interac now and move missed payment to end of loan",
        8: f"send $50 fee Interac now and split missed payment over next 2 payments",
        9: "no Interac now, missed + fee added to next payment",
        10: "no Interac now, missed next payment and fee moved to end of loan",
        11: "no Interac now, missed split in next 2 payments and fee moved to end",
        12: "no Interac now, fee next payment and missed moved to end of loan",
        13: "no Interac now, fee split next 2 payments and missed moved to end",
        14: "final option: resume regular payments, missed + fee moved to loan end",
    }
    offer = offer_lines.get(level, offer_lines[14])

    tone = _FOLLOWUP_TONE_VARIANTS[min(no_reply_count, len(_FOLLOWUP_TONE_VARIANTS) - 1)]
    stop_payment_suffix = ""
    if reason_code in _STOP_PAYMENT_CODES:
        stop_payment_suffix = " Also confirm your bank removed the stop-payment block."
    elif reason_code in _CLOSED_ACCOUNT_CODES:
        stop_payment_suffix = " Also send your new void cheque/PAD details so payments can resume."

    strict_suffix = ""
    policy = _policy_flags()
    if policy["allow_contract_breach_language"] and (no_reply_count >= 6 or level >= 12):
        strict_suffix = " This is a contract obligation and we need your response now."
    if policy["allow_reference_escalation"] and (no_reply_count >= 10 or level >= 14):
        strict_suffix = " If there is no response, we may contact your employer/references per contract terms."

    return (
        f"{tone} {first_name}, this is Mike from iLoans. "
        f"Your missed payment is ${amounts['missed']:.2f} and fee is $50.00. "
        f"Current ask: {offer}.{stop_payment_suffix}{strict_suffix}"
    ).strip()


def _classify_message_signal(message: str, ai_intent: str | None) -> str:
    text = (message or "").lower()
    if any(k in text for k in _LEGAL_KEYWORDS):
        return "legal_stop"
    if ai_intent == "promise_to_pay" or any(k in text for k in _AGREEMENT_KEYWORDS):
        return "agreement"
    if ai_intent == "refusal" or any(k in text for k in _REFUSAL_KEYWORDS):
        return "refusal"
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

    for case in cases:
        try:
            is_daily = _is_daily_reject_case(case)
            ai_generated = False
            if is_daily:
                meta = _extract_meta(case)
                level = max(1, min(14, int(meta.get("proposal_level", "1"))))
                no_reply_count = int(meta.get("no_reply_count", "0")) + 1
                message = _apply_risk_policy(_build_daily_reject_offer(case, level=level, no_reply_count=no_reply_count))
            else:
                ai_message = orchestrator.generate_outbound_message("sms", _build_case_context(case))
                message = ai_message.get("message") or (
                    f"Reminder: Payment of ${case.get_remaining_balance():.2f} is due on your account."
                )
                message = _apply_risk_policy(message)
                ai_generated = bool(ai_message.get("status") == "success")
                no_reply_count = 0
                level = 1

            duplicate_exists = InteractionLedger.objects.filter(
                collection_case=case,
                interaction_type=InteractionLedger.InteractionType.OUTBOUND,
                channel=InteractionLedger.CommunicationChannel.SMS,
                message_content=message,
                created_at__gte=timezone.now() - timedelta(minutes=10),
            ).exists()
            if duplicate_exists:
                logger.info("Skipping duplicate follow-up dispatch for case %s", case.account_id)
                continue

            payload = _build_dispatch_payload(
                case,
                message,
                subject="Collection Reminder",
                ai_generated=ai_generated,
            )
            channel = _select_outbound_channel(case)
            router.send_message(channel=channel, payload=payload)

            next_run = timezone.now() + timedelta(hours=1) if is_daily else timezone.now() + timedelta(days=3)
            case.next_action_time = next_run
            case.next_followup_at = next_run
            case.last_contact_at = timezone.now()

            if is_daily:
                target_step = _proposal_level_to_step(level)
                if case.current_workflow_step != target_step:
                    case.current_workflow_step = target_step
                    case.workflow_step_started_at = timezone.now()
                _append_case_meta(
                    case,
                    {
                        "proposal_level": level,
                        "no_reply_count": no_reply_count,
                        "last_outreach_at": timezone.now().isoformat(),
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
        ai_result = orchestrator.process_borrower_message(message, _build_case_context(case))
        intent_data = ai_result.get("intent", {})
        intent = intent_data.get("intent")
        signal = _classify_message_signal(message, intent)

        interaction.ai_intent_detected = signal if signal != "neutral" else intent
        interaction.ai_sentiment_score = intent_data.get("confidence")
        interaction.ai_processed_at = timezone.now()
        interaction.status = InteractionLedger.InteractionStatus.REPLIED
        interaction.reply_message = ai_result.get("suggested_response", {}).get("message")
        interaction.save()

        suggested_message = ""
        if _is_daily_reject_case(case):
            meta = _extract_meta(case)
            level = max(1, min(14, int(meta.get("proposal_level", "1"))))

            if signal == "legal_stop":
                case.automation_status = CollectionCase.AutomationStatus.STOPPED
                _append_case_meta(case, {"automation_stop_reason": "legal_trigger"})
            elif signal == "refusal":
                level = min(14, level + 1)
                target_step = _proposal_level_to_step(level)
                case.current_workflow_step = target_step
                case.workflow_step_started_at = timezone.now()
                suggested_message = _apply_risk_policy(_build_daily_reject_offer(case, level=level, no_reply_count=0))
                _append_case_meta(case, {"proposal_level": level, "no_reply_count": 0})
            elif signal == "agreement":
                promised_date = (timezone.now() + timedelta(days=1)).date()
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
                _append_case_meta(case, {"no_reply_count": 0})
                suggested_message = _apply_risk_policy(
                    "Thanks for confirming. Please send payment as agreed today so we can close this item."
                )
            else:
                _append_case_meta(case, {"no_reply_count": 0})
                suggested_message = _apply_risk_policy(_build_daily_reject_offer(case, level=level, no_reply_count=0))
        else:
            if intent == "refusal":
                state_machine = WorkflowStateMachine(WorkflowState[case.current_workflow_step])
                if state_machine.transition(WorkflowActions.BORROWER_REFUSED):
                    case.current_workflow_step = state_machine.current_state.value
                    case.workflow_step_started_at = timezone.now()
            elif intent == "promise_to_pay":
                promised_date = (timezone.now() + timedelta(days=3)).date()
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

        case.last_contact_at = timezone.now()
        case.next_action_time = timezone.now() + timedelta(hours=1 if _is_daily_reject_case(case) else 2)
        case.next_followup_at = case.next_action_time
        case.save()

        if suggested_message and case.automation_status == CollectionCase.AutomationStatus.ACTIVE:
            router = CommunicationRouter()
            payload = _build_dispatch_payload(
                case,
                suggested_message,
                subject="Account Update",
                ai_generated=not _is_daily_reject_case(case),
            )
            outbound_channel = _select_outbound_channel(case)
            router.send_message(outbound_channel, payload)

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
