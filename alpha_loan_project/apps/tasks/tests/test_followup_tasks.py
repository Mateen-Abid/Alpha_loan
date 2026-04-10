from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import re
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.collections.models import CollectionCase, InteractionLedger, PaymentCommitment
from apps.tasks.followup_tasks import process_borrower_message, send_followup_messages


_KV_PATTERN = re.compile(r"([a-zA-Z0-9_]+)=([^;\n]+)")


def _meta(notes: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, value in _KV_PATTERN.findall(notes or ""):
        values[key] = value.strip()
    return values


@override_settings(
    AUTO_REPLY_MODE="allowlist",
    AUTO_REPLY_ALLOWED_ROW_IDS="269062",
    COLLECTION_FOLLOWUP_INTERVAL_HOURS=1,
    COLLECTION_PROPOSAL_WINDOW_HOURS=24,
    COLLECTION_MAX_WAVE_LEVEL=5,
)
class FollowupTaskRulesTests(TestCase):
    def _create_case(
        self,
        *,
        row_id: str = "269062",
        notes_suffix: str = "",
        next_action_hours_ago: int = 2,
    ) -> CollectionCase:
        notes = (
            "board_id=70; group_id=91; ingest_reason_code=STOP_PMT; "
            "proposal_level=1; no_reply_count=0; wave_level=1; "
            f"proposal_deadline_at={(timezone.now() + timedelta(hours=24)).isoformat()}; "
            "last_missed_due=100.00"
        )
        if notes_suffix:
            notes = f"{notes}\n{notes_suffix}"

        return CollectionCase.objects.create(
            account_id=f"case-{row_id}-{CollectionCase.objects.count() + 1}",
            partner_row_id=row_id,
            borrower_name="John Doe",
            borrower_email="john@example.com",
            borrower_phone="+15145551234",
            principal_amount=Decimal("100.00"),
            total_due=Decimal("150.00"),
            delinquent_date=timezone.now().date() - timedelta(days=3),
            current_workflow_step=CollectionCase.WorkflowStep.STEP_1,
            status=CollectionCase.CollectionStatus.ACTIVE,
            automation_status=CollectionCase.AutomationStatus.ACTIVE,
            next_action_time=timezone.now() - timedelta(hours=next_action_hours_ago),
            next_followup_at=timezone.now() - timedelta(hours=next_action_hours_ago),
            notes=notes,
        )

    def _create_inbound_interaction(self, case: CollectionCase, message: str) -> InteractionLedger:
        return InteractionLedger.objects.create(
            collection_case=case,
            channel=InteractionLedger.CommunicationChannel.SMS,
            interaction_type=InteractionLedger.InteractionType.INBOUND,
            status=InteractionLedger.InteractionStatus.REPLIED,
            message_content=message,
        )

    @patch("apps.tasks.followup_tasks.CommunicationRouter.send_message", return_value={"status": "success", "external_id": "x1"})
    def test_send_followup_keeps_same_proposal_before_deadline(self, mock_send):
        case = self._create_case()

        send_followup_messages.run()

        case.refresh_from_db()
        meta = _meta(case.notes)
        self.assertEqual(meta.get("proposal_level"), "1")
        self.assertEqual(meta.get("no_reply_count"), "1")
        self.assertEqual(meta.get("wave_level"), "2")
        self.assertEqual(mock_send.call_count, 1)
        payload = mock_send.call_args.kwargs["payload"]
        self.assertIn("Interac now", payload["message"])

    @patch("apps.tasks.followup_tasks.CommunicationRouter.send_message", return_value={"status": "success", "external_id": "x2"})
    def test_send_followup_moves_to_next_proposal_after_deadline(self, mock_send):
        deadline_in_past = f"proposal_deadline_at={(timezone.now() - timedelta(hours=1)).isoformat()}"
        case = self._create_case(notes_suffix=deadline_in_past)

        send_followup_messages.run()

        case.refresh_from_db()
        meta = _meta(case.notes)
        self.assertEqual(meta.get("proposal_level"), "2")
        self.assertEqual(meta.get("no_reply_count"), "1")
        payload = mock_send.call_args.kwargs["payload"]
        self.assertIn("end of day", payload["message"])

    @patch("apps.tasks.followup_tasks.CommunicationRouter.send_message")
    def test_send_followup_respects_allowlist_gate(self, mock_send):
        case = self._create_case(row_id="999999")
        original_next_action = case.next_action_time

        send_followup_messages.run()

        case.refresh_from_db()
        self.assertEqual(mock_send.call_count, 0)
        self.assertEqual(case.next_action_time, original_next_action)

    @patch("apps.tasks.followup_tasks.CommunicationRouter.send_message", return_value={"status": "success", "external_id": "x3"})
    @patch(
        "apps.tasks.followup_tasks.AIOrchestrator.process_borrower_message",
        return_value={
            "intent": {"intent": "refusal", "confidence": 0.91},
            "suggested_response": {"message": "No"},
        },
    )
    def test_process_borrower_refusal_advances_proposal_level(self, _mock_ai, mock_send):
        case = self._create_case()
        interaction = self._create_inbound_interaction(case, "i will not pay")

        process_borrower_message.run(case.id, interaction.id, "i will not pay", "sms")

        case.refresh_from_db()
        meta = _meta(case.notes)
        self.assertEqual(meta.get("proposal_level"), "2")
        self.assertEqual(meta.get("no_reply_count"), "0")
        self.assertEqual(mock_send.call_count, 1)
        payload = mock_send.call_args.kwargs.get("payload") or mock_send.call_args.args[1]
        self.assertIn("end of day", payload["message"])

    @patch("apps.tasks.followup_tasks.CommunicationRouter.send_message", return_value={"status": "success", "external_id": "x4"})
    @patch(
        "apps.tasks.followup_tasks.AIOrchestrator.process_borrower_message",
        return_value={
            "intent": {"intent": "promise_to_pay", "confidence": 0.88},
            "suggested_response": {"message": "i will pay today"},
        },
    )
    def test_process_borrower_agreement_creates_commitment_and_pauses_case(self, _mock_ai, mock_send):
        case = self._create_case()
        interaction = self._create_inbound_interaction(case, "i will pay today")

        process_borrower_message.run(case.id, interaction.id, "i will pay today", "sms")

        case.refresh_from_db()
        self.assertEqual(case.automation_status, CollectionCase.AutomationStatus.PAUSED)
        self.assertEqual(PaymentCommitment.objects.filter(collection_case=case).count(), 1)
        self.assertEqual(mock_send.call_count, 1)
