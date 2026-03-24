"""Follow-up Tasks - Scheduled follow-up messaging and inbound AI handling."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Dict

from celery import shared_task
from django.utils import timezone

from apps.ai.services.ai_orchestrator import AIOrchestrator
from apps.collections.models import CollectionCase, InteractionLedger, PaymentCommitment
from apps.collections.services.collection_service import CollectionService
from apps.collections.workflows.state_machine import WorkflowStateMachine
from apps.collections.workflows.workflow_states import WorkflowActions, WorkflowState
from apps.communications.services.communication_router import CommunicationRouter, ExternalDispatchError

logger = logging.getLogger(__name__)


def _build_case_context(case: CollectionCase) -> Dict[str, object]:
    return {
        "total_due": case.total_due,
        "current_workflow_step": case.current_workflow_step,
        "days_delinquent": case.get_age_in_days(),
        "borrower_name": case.borrower_name,
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


@shared_task(bind=True, autoretry_for=(ExternalDispatchError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def send_followup_messages(self):
    """
    Send follow-up messages for active automation cases.
    Idempotent behavior: skip if a matching outbound message already exists recently.
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
            ai_message = orchestrator.generate_outbound_message("sms", _build_case_context(case))
            message = ai_message.get("message") or (
                f"Reminder: Payment of ${case.get_remaining_balance():.2f} is due on your account."
            )

            duplicate_exists = InteractionLedger.objects.filter(
                collection_case=case,
                interaction_type=InteractionLedger.InteractionType.OUTBOUND,
                channel=InteractionLedger.CommunicationChannel.SMS,
                message_content=message,
                created_at__gte=timezone.now() - timedelta(minutes=5),
            ).exists()
            if duplicate_exists:
                logger.info("Skipping duplicate follow-up dispatch for case %s", case.account_id)
                continue

            payload = _build_dispatch_payload(
                case,
                message,
                subject="Collection Reminder",
                ai_generated=bool(ai_message.get("status") == "success"),
            )
            channel = _select_outbound_channel(case)
            router.send_message(channel=channel, payload=payload)

            next_run = timezone.now() + timedelta(days=3)
            case.next_action_time = next_run
            case.next_followup_at = next_run
            case.last_contact_at = timezone.now()
            case.save(update_fields=["next_action_time", "next_followup_at", "last_contact_at", "updated_at"])

            logger.info("Follow-up message sent for case %s", case.account_id)
        except Exception as exc:
            logger.error("Error sending follow-up for case %s: %s", case.account_id, str(exc))
            raise


@shared_task(bind=True, autoretry_for=(ExternalDispatchError,), retry_backoff=True, retry_jitter=True, max_retries=5)
def process_borrower_message(self, case_id: int, interaction_id: int, message: str, channel: str = "sms"):
    """
    Process inbound borrower message with AI intent + response handling.
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

        interaction.ai_intent_detected = intent
        interaction.ai_sentiment_score = intent_data.get("confidence")
        interaction.ai_processed_at = timezone.now()
        interaction.status = InteractionLedger.InteractionStatus.REPLIED
        interaction.reply_message = ai_result.get("suggested_response", {}).get("message")
        interaction.save()

        if intent == "refusal":
            state_machine = WorkflowStateMachine(WorkflowState[case.current_workflow_step])
            if state_machine.transition(WorkflowActions.BORROWER_REFUSED):
                case.current_workflow_step = state_machine.current_state.value
                case.workflow_step_started_at = timezone.now()
                logger.info(f"Workflow advanced for case {case.account_id}")

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

        case.last_contact_at = timezone.now()
        case.next_action_time = timezone.now() + timedelta(days=2)
        case.next_followup_at = case.next_action_time
        case.save(
            update_fields=[
                "current_workflow_step",
                "workflow_step_started_at",
                "last_contact_at",
                "next_action_time",
                "next_followup_at",
                "updated_at",
            ]
        )

        suggested = ai_result.get("suggested_response", {})
        suggested_message = suggested.get("message")
        if suggested_message:
            router = CommunicationRouter()
            payload = _build_dispatch_payload(
                case,
                suggested_message,
                subject="Account Update",
                ai_generated=True,
            )
            outbound_channel = _select_outbound_channel(case)
            router.send_message(outbound_channel, payload)

        logger.info("Processed message for case %s, intent: %s", case.account_id, intent)
        return {"status": "success", "intent": intent}
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
