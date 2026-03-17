"""Promise to Pay Tasks - Commitment fulfillment tracking"""

from celery import shared_task
from django.utils import timezone
from apps.collections.models import PaymentCommitment
import logging

logger = logging.getLogger(__name__)


@shared_task
def check_commitment_fulfillment():
    """
    Check if payment commitments were fulfilled.
    Mark broken commitments and trigger escalation.
    """
    from datetime import timedelta
    
    past_commitments = PaymentCommitment.objects.filter(
        status__in=['PENDING', 'CONFIRMED'],
        promised_date__lt=timezone.now().date()
    )
    
    for commitment in past_commitments:
        if commitment.amount_paid >= commitment.committed_amount:
            commitment.status = 'FULFILLED'
        else:
            commitment.status = 'BROKEN'
        
        commitment.save()
        
        if commitment.status == 'BROKEN':
            # Trigger workflow escalation
            case = commitment.collection_case
            from apps.collections.workflows.workflow_states import WorkflowState, WorkflowActions
            from apps.collections.workflows.state_machine import WorkflowStateMachine
            
            state_machine = WorkflowStateMachine(
                WorkflowState[case.current_workflow_step]
            )
            
            if state_machine.transition(WorkflowActions.COMMITMENT_BROKEN):
                case.current_workflow_step = state_machine.current_state.value
                case.save()
                
                logger.info(f"Escalated case {case.account_id} due to broken commitment")


@shared_task
def send_commitment_reminder():
    """Send reminders for upcoming commitments"""
    from datetime import timedelta
    from apps.communications.services.communication_router import CommunicationRouter
    
    tomorrow = timezone.now().date() + timedelta(days=1)
    commitments = PaymentCommitment.objects.filter(
        status__in=['PENDING', 'CONFIRMED'],
        promised_date=tomorrow
    )
    
    router = CommunicationRouter()
    
    for commitment in commitments:
        case = commitment.collection_case
        message = f"Reminder: Payment of ${commitment.committed_amount:.2f} is due tomorrow."
        
        try:
            router.send_message(
                channel='sms',
                payload={
                    "row_id": case.partner_row_id or case.account_id,
                    "case_id": case.id,
                    "phone": case.borrower_phone,
                    "email": case.borrower_email,
                    "message": message,
                    "subject": "Commitment Reminder",
                },
            )
            logger.info(f"Reminder sent for commitment {commitment.id}")
        except Exception as e:
            logger.error(f"Error sending reminder: {str(e)}")
