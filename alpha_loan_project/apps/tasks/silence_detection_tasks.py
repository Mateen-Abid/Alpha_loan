"""Silence Detection Tasks - Track contact attempts"""

from celery import shared_task
from django.utils import timezone
from apps.collections.models import CollectionCase, InteractionLedger
import logging

logger = logging.getLogger(__name__)


@shared_task
def detect_silence_periods():
    """
    Detect cases with no recent contact and flag them.
    Triggers additional outreach for silent borrowers.
    """
    from datetime import timedelta
    
    silence_threshold = timezone.now() - timedelta(days=7)
    
    silent_cases = CollectionCase.objects.filter(
        status='ACTIVE',
        last_contact_at__lte=silence_threshold
    )
    
    for case in silent_cases:
        # Flag for manual review or escalated outreach
        logger.warning(f"Silence detected on case {case.account_id} - last contact {case.last_contact_at}")
        
        # Could trigger escalated collection attempts
        attempt_escalated_contact.delay(case.id)


@shared_task
def attempt_escalated_contact(case_id: int):
    """Attempt escalated contact via multiple channels"""
    try:
        case = CollectionCase.objects.get(id=case_id)
        
        from apps.communications.services.communication_router import CommunicationRouter
        router = CommunicationRouter()
        
        message = f"Important: Your account requires immediate attention. Please contact us."
        
        # Try SMS first
        router.send_message(
            channel='sms',
            payload={
                "row_id": case.partner_row_id or case.account_id,
                "case_id": case.id,
                "phone": case.borrower_phone,
                "email": case.borrower_email,
                "message": message,
                "subject": "Urgent Account Notice",
            },
        )
        
        # If email exists, also send email
        if case.borrower_email:
            router.send_message(
                channel='email',
                payload={
                    "row_id": case.partner_row_id or case.account_id,
                    "case_id": case.id,
                    "phone": case.borrower_phone,
                    "email": case.borrower_email,
                    "message": message,
                    "subject": "Urgent Account Notice",
                },
            )
        
        logger.info(f"Escalated contact attempted for case {case.account_id}")
    except Exception as e:
        logger.error(f"Error in escalated contact: {str(e)}")
