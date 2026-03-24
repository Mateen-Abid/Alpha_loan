"""Promise to Pay Tasks - Commitment fulfillment tracking"""

from datetime import timedelta
import logging

from celery import shared_task
from django.utils import timezone

from apps.collections.models import PaymentCommitment
from apps.collections.workflows.state_machine import WorkflowStateMachine
from apps.collections.workflows.workflow_states import WorkflowActions, WorkflowState
from apps.communications.services.communication_router import CommunicationRouter

logger = logging.getLogger(__name__)


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
            
            state_machine = WorkflowStateMachine(
                WorkflowState[case.current_workflow_step]
            )
            
            if state_machine.transition(WorkflowActions.COMMITMENT_BROKEN):
                case.current_workflow_step = state_machine.current_state.value
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
