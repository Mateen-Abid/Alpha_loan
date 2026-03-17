"""Webhook Processor - Routes payloads, persists interactions, enqueues AI tasks."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
import logging
from typing import Any, Dict, Optional

from django.db import transaction
from django.utils import timezone

from apps.collections.models import CollectionCase, InteractionLedger, TransactionLedger
from apps.collections.services.collection_service import CollectionService
from apps.communications.services.communication_router import CommunicationRouter


logger = logging.getLogger(__name__)
ALLOWED_BOARD_IDS = {70, 71, 73, 74}


class WebhookProcessor:
    """Processes received webhooks and orchestrates handlers."""

    @staticmethod
    def queue_sms_processing(case_id: int, interaction_id: int, message: str) -> None:
        """Queue borrower message for async AI processing."""
        from apps.tasks.followup_tasks import process_borrower_message

        process_borrower_message.delay(case_id, interaction_id, message, "sms")

    @staticmethod
    def queue_voice_processing(case_id: int, interaction_id: int, transcript: str) -> None:
        """Queue voice transcript for async AI processing."""
        from apps.tasks.followup_tasks import process_voice_transcript

        process_voice_transcript.delay(case_id, interaction_id, transcript)

    @staticmethod
    def route_webhook(webhook_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route webhook to processing branch."""
        if webhook_type == "sms":
            return WebhookProcessor._process_inbound_message(payload=payload, channel="SMS")
        if webhook_type == "email":
            return WebhookProcessor._process_inbound_message(payload=payload, channel="EMAIL")
        if webhook_type == "voice":
            return WebhookProcessor._process_voice(payload)
        if webhook_type == "crm":
            return WebhookProcessor._process_crm_ingestion(payload)
        return {"status": "failed", "error": f"Unknown webhook type: {webhook_type}"}

    @staticmethod
    def _resolve_case(payload: Dict[str, Any]) -> Optional[CollectionCase]:
        nested_data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        phone = (
            payload.get("phone")
            or payload.get("from_phone")
            or payload.get("from")
            or payload.get("to")
            or nested_data.get("phone")
        )
        email = payload.get("email") or payload.get("from_email") or payload.get("from") or nested_data.get("email")
        return CollectionService.find_case(
            row_id=payload.get("row_id") or nested_data.get("row_id"),
            phone=phone,
            email=email,
        )

    @staticmethod
    def _existing_interaction(external_id: Optional[str]) -> Optional[InteractionLedger]:
        if not external_id:
            return None
        return InteractionLedger.objects.filter(external_id=external_id).first()

    @staticmethod
    def _process_inbound_message(payload: Dict[str, Any], channel: str) -> Dict[str, Any]:
        case = WebhookProcessor._resolve_case(payload)
        if not case:
            return {"status": "ignored", "reason": "case_not_found"}

        message = payload.get("message") or payload.get("body") or ""
        if not message:
            return {"status": "ignored", "reason": "empty_message"}

        external_id = payload.get("message_id") or payload.get("external_id")
        existing = WebhookProcessor._existing_interaction(external_id)
        if existing:
            return {"status": "success", "interaction_id": existing.id, "idempotent": True}

        with transaction.atomic():
            interaction = CollectionService.record_interaction(
                case=case,
                channel=channel,
                interaction_type=InteractionLedger.InteractionType.INBOUND,
                message_content=message,
                external_id=external_id,
                subject=payload.get("subject", ""),
                status=InteractionLedger.InteractionStatus.REPLIED,
            )
            case.last_contact_at = timezone.now()
            case.save(update_fields=["last_contact_at", "updated_at"])

        from apps.tasks.followup_tasks import process_borrower_message

        process_borrower_message.delay(case.id, interaction.id, message, channel.lower())
        return {"status": "success", "interaction_id": interaction.id}

    @staticmethod
    def _process_voice(payload: Dict[str, Any]) -> Dict[str, Any]:
        case = WebhookProcessor._resolve_case(payload)
        if not case:
            return {"status": "ignored", "reason": "case_not_found"}

        transcript = payload.get("transcript") or ""
        external_id = payload.get("call_id")
        existing = WebhookProcessor._existing_interaction(external_id)
        if existing:
            return {"status": "success", "interaction_id": existing.id, "idempotent": True}

        with transaction.atomic():
            interaction = CollectionService.record_interaction(
                case=case,
                channel=InteractionLedger.CommunicationChannel.VOICE,
                interaction_type=InteractionLedger.InteractionType.INBOUND,
                message_content=transcript or "Voice call completed",
                external_id=external_id,
                status=InteractionLedger.InteractionStatus.REPLIED if transcript else InteractionLedger.InteractionStatus.DELIVERED,
            )
            case.last_contact_at = timezone.now()
            case.save(update_fields=["last_contact_at", "updated_at"])

        if transcript:
            WebhookProcessor.queue_voice_processing(case.id, interaction.id, transcript)
        return {"status": "success", "interaction_id": interaction.id}

    @staticmethod
    def _process_crm_ingestion(payload: Dict[str, Any]) -> Dict[str, Any]:
        nested_data = payload.get("data", {}) if isinstance(payload.get("data"), dict) else {}
        row_id = str(payload.get("row_id") or nested_data.get("row_id") or "").strip()
        if not row_id:
            return {"status": "failed", "error": "row_id is required"}

        board_id_raw = payload.get("board_id") or nested_data.get("board_id")
        if board_id_raw is not None:
            try:
                board_id = int(board_id_raw)
            except (TypeError, ValueError):
                return {"status": "failed", "error": "board_id is invalid"}
            if board_id not in ALLOWED_BOARD_IDS:
                return {"status": "failed", "error": "Row is outside allowed Daily/E-Transfer board scope."}

        try:
            failed_payment_amount = Decimal(
                str(payload.get("failed_payment_amount") or nested_data.get("failed_payment_amount") or "0")
            )
        except (InvalidOperation, TypeError):
            return {"status": "failed", "error": "failed_payment_amount is invalid"}

        phone = str(payload.get("phone") or nested_data.get("phone") or "").strip()
        fallback_phone = "0000000000"
        email = str(payload.get("email") or nested_data.get("email") or "").strip()
        borrower_name = str(
            payload.get("borrower_name")
            or nested_data.get("borrower_name")
            or payload.get("name")
            or f"Borrower {row_id}"
        ).strip()
        return_reason = str(payload.get("return_reason") or nested_data.get("return_reason") or "").strip()

        with transaction.atomic():
            case = CollectionCase.objects.filter(partner_row_id=row_id).first()
            if not case:
                case = CollectionCase.objects.create(
                    account_id=f"row-{row_id}",
                    partner_row_id=row_id,
                    borrower_name=borrower_name,
                    borrower_email=email or None,
                    borrower_phone=(phone or fallback_phone)[:20],
                    principal_amount=failed_payment_amount,
                    total_due=failed_payment_amount,
                    delinquent_date=timezone.now().date(),
                    current_workflow_step=CollectionCase.WorkflowStep.STEP_1,
                    status=CollectionCase.CollectionStatus.ACTIVE,
                    automation_status=CollectionCase.AutomationStatus.ACTIVE,
                    next_action_time=timezone.now(),
                )
            else:
                case.borrower_email = email or case.borrower_email
                case.borrower_phone = (phone or case.borrower_phone or fallback_phone)[:20]
                case.total_due = max(case.total_due, failed_payment_amount)
                case.partner_row_id = row_id
                case.current_workflow_step = CollectionCase.WorkflowStep.STEP_1
                case.workflow_step_started_at = timezone.now()
                case.automation_status = CollectionCase.AutomationStatus.ACTIVE
                case.next_action_time = timezone.now()
                case.save()

            txn_exists = TransactionLedger.objects.filter(
                collection_case=case,
                transaction_type=TransactionLedger.TransactionType.NSF,
                amount=failed_payment_amount,
                posted_date=date.today(),
                external_reference=row_id,
            ).exists()
            if not txn_exists:
                TransactionLedger.objects.create(
                    collection_case=case,
                    transaction_type=TransactionLedger.TransactionType.NSF,
                    amount=failed_payment_amount,
                    posted_date=date.today(),
                    description=f"Failed payment ingest. Reason: {return_reason}",
                    created_by="crm_webhook",
                    external_reference=row_id,
                )

        initial_message = (
            f"Payment failure detected (${failed_payment_amount:.2f}). "
            "Please resolve your account to avoid escalation."
        )
        router = CommunicationRouter()
        outbound_payload = {
            "row_id": row_id,
            "case_id": case.id,
            "phone": case.borrower_phone,
            "email": case.borrower_email,
            "message": initial_message,
            "subject": "Initial Collection Notice",
            "ai_generated": False,
        }

        recent_duplicate = InteractionLedger.objects.filter(
            collection_case=case,
            interaction_type=InteractionLedger.InteractionType.OUTBOUND,
            message_content=initial_message,
            created_at__gte=timezone.now() - timedelta(minutes=5),
        ).exists()
        if not recent_duplicate:
            if case.borrower_phone:
                router.send_message("sms", outbound_payload)
            elif case.borrower_email:
                router.send_message("email", outbound_payload)

        return {"status": "success", "case_id": case.id, "row_id": row_id}
