"""Silence Detection Tasks - Track contact attempts"""

from datetime import timedelta
import logging

from celery import shared_task
from django.utils import timezone

from apps.collections.models import CollectionCase

logger = logging.getLogger(__name__)


@shared_task
def detect_silence_periods():
    """
    Detect cases with no recent contact and flag them.
    Triggers additional outreach for silent borrowers.
    """
    silence_threshold = timezone.now() - timedelta(days=7)
    
    silent_cases = CollectionCase.objects.filter(
        status=CollectionCase.CollectionStatus.ACTIVE,
        last_contact_at__lte=silence_threshold,
    )
    
    for case in silent_cases:
        # Flag for manual review or escalated outreach
        logger.warning(
            "Silence detected on case %s - last contact %s",
            case.account_id,
            case.last_contact_at,
        )
        
        # Could trigger escalated collection attempts
        attempt_escalated_contact.delay(case.id)


@shared_task
def attempt_escalated_contact(case_id: int):
    """Attempt escalated contact via multiple channels"""
    try:
        case = CollectionCase.objects.get(id=case_id)
        
        from apps.communications.services.communication_router import CommunicationRouter

        router = CommunicationRouter()
        message = "Important: Your account requires immediate attention. Please contact us."
        
        # Try SMS first
        router.send_message(
            channel="sms",
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
                channel="email",
                payload={
                    "row_id": case.partner_row_id or case.account_id,
                    "case_id": case.id,
                    "phone": case.borrower_phone,
                    "email": case.borrower_email,
                    "message": message,
                    "subject": "Urgent Account Notice",
                },
            )
        
        logger.info("Escalated contact attempted for case %s", case.account_id)
    except Exception as exc:
        logger.error("Error in escalated contact: %s", str(exc))
