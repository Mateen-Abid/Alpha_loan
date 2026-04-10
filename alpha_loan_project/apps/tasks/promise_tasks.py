"""Promise to Pay Tasks - Commitment fulfillment tracking"""

from datetime import timedelta
import logging
import re

from celery import shared_task
from django.utils import timezone

from apps.collections.models import PaymentCommitment
from apps.collections.workflows.state_machine import WorkflowStateMachine
from apps.collections.workflows.workflow_states import WorkflowActions, WorkflowState
from apps.communications.services.communication_router import CommunicationRouter

logger = logging.getLogger(__name__)
_KV_PATTERN = re.compile(r"([a-zA-Z0-9_]+)=([^;\n]+)")


def _extract_meta(notes: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in _KV_PATTERN.findall(notes or ""):
        values[key] = value.strip()
    return values


def _append_meta(case, updates: dict[str, object]) -> None:
    payload = "; ".join(f"{k}={v}" for k, v in updates.items())
    case.notes = f"{case.notes}\n{payload}".strip() if case.notes else payload


def _safe_int(value: object, default: int = 1, min_value: int = 1, max_value: int = 14) -> int:
    try:
        parsed = int(str(value).strip())
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _is_daily_reject_case(case) -> bool:
    notes = (case.notes or "").lower()
    return "board_id=70" in notes and "group_id=91" in notes


def _proposal_level_to_step(case, level: int) -> str:
    if level <= 3:
        return case.WorkflowStep.STEP_1
    if level <= 6:
        return case.WorkflowStep.STEP_2
    if level <= 10:
        return case.WorkflowStep.STEP_3
    if level <= 13:
        return case.WorkflowStep.STEP_4
    return case.WorkflowStep.FINAL_PRESSURE


@shared_task
def check_commitment_fulfillment():
    """
    Check if payment commitments were fulfilled.
    Mark broken commitments and trigger escalation.
    """
    past_commitments = PaymentCommitment.objects.filter(
        status__in=[
            PaymentCommitment.CommitmentStatus.PENDING,
            PaymentCommitment.CommitmentStatus.CONFIRMED,
        ],
        promised_date__lt=timezone.now().date(),
    )
    
    for commitment in past_commitments:
        if commitment.amount_paid >= commitment.committed_amount:
            commitment.status = PaymentCommitment.CommitmentStatus.FULFILLED
        else:
            commitment.status = PaymentCommitment.CommitmentStatus.BROKEN
        
        commitment.save()
        
        if commitment.status == PaymentCommitment.CommitmentStatus.BROKEN:
            # Trigger workflow escalation
            case = commitment.collection_case
            now = timezone.now()
            case.automation_status = case.AutomationStatus.ACTIVE
            case.last_contact_at = now
            case.next_action_time = now + timedelta(hours=1)
            case.next_followup_at = case.next_action_time

            if _is_daily_reject_case(case):
                meta = _extract_meta(case.notes or "")
                level = _safe_int(meta.get("proposal_level", "1"))
                level = min(14, level + 1)
                case.current_workflow_step = _proposal_level_to_step(case, level)
                case.workflow_step_started_at = now
                _append_meta(
                    case,
                    {
                        "proposal_level": level,
                        "no_reply_count": 0,
                        "promise_status": "broken",
                        "proposal_deadline_at": (now + timedelta(hours=24)).isoformat(),
                    },
                )
            else:
                state_machine = WorkflowStateMachine(
                    WorkflowState[case.current_workflow_step]
                )
                if state_machine.transition(WorkflowActions.COMMITMENT_BROKEN):
                    case.current_workflow_step = state_machine.current_state.value
                    case.workflow_step_started_at = now

            case.save()
            logger.info("Escalated case %s due to broken commitment", case.account_id)


@shared_task
def send_commitment_reminder():
    """Send reminders for upcoming commitments"""

    tomorrow = timezone.now().date() + timedelta(days=1)
    commitments = PaymentCommitment.objects.filter(
        status__in=[
            PaymentCommitment.CommitmentStatus.PENDING,
            PaymentCommitment.CommitmentStatus.CONFIRMED,
        ],
        promised_date=tomorrow,
    )
    
    router = CommunicationRouter()
    
    for commitment in commitments:
        case = commitment.collection_case
        message = f"Reminder: Payment of ${commitment.committed_amount:.2f} is due tomorrow."
        
        try:
            router.send_message(
                channel="sms",
                payload={
                    "row_id": case.partner_row_id or case.account_id,
                    "case_id": case.id,
                    "phone": case.borrower_phone,
                    "email": case.borrower_email,
                    "message": message,
                    "subject": "Commitment Reminder",
                },
            )
            logger.info("Reminder sent for commitment %s", commitment.id)
        except Exception as exc:
            logger.error("Error sending reminder: %s", str(exc))
