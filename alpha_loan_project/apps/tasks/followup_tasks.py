"""Follow-up Tasks - Scheduled follow-up messaging"""

from celery import shared_task
from django.utils import timezone
from apps.collections.models import CollectionCase
from apps.communications.services.communication_router import CommunicationRouter
from apps.collections.workflows.workflow_states import WorkflowState, WorkflowActions
from apps.collections.workflows.state_machine import WorkflowStateMachine
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_followup_messages():
    """
    Scheduled task to send follow-up messages to cases needing contact.
    Runs based on next_followup_at timestamp.
    """
    cases = CollectionCase.objects.filter(
        status='ACTIVE',
        next_followup_at__lte=timezone.now()
    )
    
    router = CommunicationRouter()
    
    for case in cases:
        try:
            # Determine preferred channel (default to SMS)
            channel = 'sms'  # Could be stored as preference
            
            message = f"Reminder: Payment of ${case.get_remaining_balance():.2f} is due on your account."
            
            result = router.send_message(
                channel=channel,
                recipient=case.borrower_phone if channel == 'sms' else case.borrower_email,
                message=message,
                case_id=case.account_id
            )
            
            if result.get('status') == 'success':
                # Schedule next follow-up (3 days later)
                case.next_followup_at = timezone.now() + timezone.timedelta(days=3)
                case.save()
            
            logger.info(f"Follow-up message sent for case {case.account_id}")
        except Exception as e:
            logger.error(f"Error sending follow-up for case {case.account_id}: {str(e)}")


@shared_task
def process_borrowed_message(case_id: int, interaction_id: int, message: str):
    """
    Process incoming borrower message using AI.
    Detects intent and may trigger workflow transitions.
    """
    try:
        from apps.collections.models import InteractionLedger
        from apps.ai.services.ai_orchestrator import AIOrchestrator
        
        case = CollectionCase.objects.get(id=case_id)
        interaction = InteractionLedger.objects.get(id=interaction_id)
        
        # Process message with AI
        orchestrator = AIOrchestrator()
        ai_result = orchestrator.process_borrower_message(message, {
            'total_due': case.total_due,
            'current_workflow_step': case.current_workflow_step,
            'days_delinquent': case.get_age_in_days(),
            'borrower_name': case.borrower_name
        })
        
        # Update interaction with AI analysis
        intent_data = ai_result.get('intent', {})
        interaction.ai_intent_detected = intent_data.get('intent')
        interaction.ai_sentiment_score = intent_data.get('confidence')
        interaction.ai_processed_at = timezone.now()
        interaction.status = 'REPLIED'
        interaction.save()
        
        # Handle workflow state transitions
        intent = intent_data.get('intent')
        
        if intent == 'refusal':
            # Borrower refused - advance workflow
            state_machine = WorkflowStateMachine(
                WorkflowState[case.current_workflow_step]
            )
            if state_machine.transition(WorkflowActions.BORROWER_REFUSED):
                case.current_workflow_step = state_machine.current_state.value
                case.save()
                logger.info(f"Workflow advanced for case {case.account_id}")
        
        elif intent == 'promise_to_pay':
            # Record commitment
            from apps.collections.services.collection_service import CollectionService
            from datetime import datetime, timedelta
            
            promised_date = (datetime.now() + timedelta(days=3)).date()
            CollectionService.create_payment_commitment(
                case=case,
                committed_amount=case.get_remaining_balance(),
                promised_date=promised_date,
                payment_method='Phone'
            )
        
        logger.info(f"Processed message for case {case.account_id}, intent: {intent}")
    except Exception as e:
        logger.error(f"Error processing borrowed message: {str(e)}")


@shared_task
def process_voice_transcript(case_id: int, interaction_id: int, transcript: str):
    """Process voice call transcript"""
    try:
        case = CollectionCase.objects.get(id=case_id)
        # Similar to SMS processing
        from apps.ai.services.ai_orchestrator import AIOrchestrator
        
        orchestrator = AIOrchestrator()
        ai_result = orchestrator.process_borrower_message(transcript, {
            'total_due': case.total_due,
            'current_workflow_step': case.current_workflow_step,
            'days_delinquent': case.get_age_in_days(),
            'borrower_name': case.borrower_name
        })
        
        logger.info(f"Processed voice transcript for case {case.account_id}")
    except Exception as e:
        logger.error(f"Error processing voice transcript: {str(e)}")
