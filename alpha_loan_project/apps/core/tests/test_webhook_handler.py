from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.collections.models import CRMData, IngestionData, MessagesInbound, MessagesOutbound
from apps.core.views import webhook_handler


@override_settings(ICOLLECTOR_OUTBOUND_SECRET="")
class ICollectorWebhookAutoReplyTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        webhook_handler._processed_events.clear()

    def _create_crm_and_ingestion(
        self,
        *,
        row_id: int,
        board_id: int = 70,
        group_id: int = 91,
        phone: str = "+15145551234",
    ) -> tuple[CRMData, IngestionData]:
        crm = CRMData.objects.create(
            row_id=row_id,
            board_id=board_id,
            group_id=group_id,
            client="John Doe",
            phone_number_raw=phone,
            amount=Decimal("100.00"),
            balance=Decimal("300.00"),
            reason="EFT Failed Insufficient Funds",
            wave=Decimal("1.0"),
            raw_columns_json={"Client": "John Doe"},
        )
        ingestion = IngestionData.objects.create(
            crm_data=crm,
            row_id=row_id,
            borrower="John Doe",
            phone=phone,
            amount=Decimal("100.00"),
            amount_plus_fee=Decimal("150.00"),
            balance=Decimal("300.00"),
            reason_code="NSF_1",
            wave=1,
            is_valid=True,
        )
        return crm, ingestion

    def _create_prior_outbound(self, *, row_id: int, phone: str, message: str) -> MessagesOutbound:
        return MessagesOutbound.objects.create(
            row_id=row_id,
            borrower_name="John Doe",
            phone=phone,
            channel=MessagesOutbound.Channel.SMS,
            wave=1,
            amount=Decimal("100.00"),
            total_due=Decimal("150.00"),
            reason="NSF_1",
            message_content=message,
            status=MessagesOutbound.Status.SENT,
            provider="icollector",
            sent_at=timezone.now(),
        )

    def _payload(self, *, event_id: str, row_id: int, message: str, phone: str = "+15145551234", occurred_at=None):
        return {
            "event_id": event_id,
            "event": "sms.received",
            "occurred_at": (occurred_at or (timezone.now() + timedelta(seconds=10))).isoformat(),
            "data": {
                "from_phone": phone,
                "message": message,
                "row_id": row_id,
                "message_id": f"provider-{event_id}",
            },
        }

    def test_daily_reject_inbound_triggers_autoreply_with_message_pair_context(self):
        _, ingestion = self._create_crm_and_ingestion(row_id=70001)
        prior = self._create_prior_outbound(
            row_id=70001,
            phone="+15145551234",
            message="hey John, this is mike from ilowns. your payment bounced. can you send it today?",
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={
                "answer": "hey John, thanks for the update. total due is $150.00. what exact time are you sending this today?",
                "model": "collections-gateway",
            },
        ) as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended",
            return_value={"status": "success", "sms_log": {"message_id": "sms-1"}},
        ) as mock_send:
            response = self.api_client.post("/api/webhooks/icollector/", self._payload(
                event_id="evt-pair-1",
                row_id=70001,
                message="i can pay later today",
            ), format="json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(mock_send.call_count, 1)

        prompt = mock_generate.call_args.kwargs["prompt"]
        self.assertIn(prior.message_content, prompt)
        self.assertIn("i can pay later today", prompt)
        self.assertIn("Amount due target (amount + fee when available): $150.00", prompt)
        self.assertIn("Fee amount: $50.00", prompt)

        inbound = MessagesInbound.objects.get(row_id=70001)
        self.assertTrue(inbound.is_processed)
        self.assertIsNotNone(inbound.processed_at)

        latest_outbound = MessagesOutbound.objects.filter(row_id=70001).order_by("-id").first()
        self.assertIsNotNone(latest_outbound)
        self.assertEqual(latest_outbound.status, MessagesOutbound.Status.SENT)
        self.assertIn("total due is $150.00", latest_outbound.message_content)

        ingestion.refresh_from_db()
        self.assertTrue(ingestion.message_generated)
        self.assertTrue(ingestion.message_sent)
        self.assertIsNotNone(ingestion.last_message_at)

    def test_non_daily_reject_row_stores_inbound_only(self):
        self._create_crm_and_ingestion(row_id=71001, board_id=71, group_id=91)

        with patch("apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm") as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended"
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._payload(event_id="evt-outscope-1", row_id=71001, message="hello"),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"]["auto_reply"]["status"], "skipped")
        self.assertEqual(body["result"]["auto_reply"]["reason"], "out_of_scope")
        self.assertEqual(mock_generate.call_count, 0)
        self.assertEqual(mock_send.call_count, 0)
        self.assertEqual(MessagesInbound.objects.count(), 1)

    def test_idempotent_replay_does_not_send_duplicate_outbound(self):
        self._create_crm_and_ingestion(row_id=70002)
        self._create_prior_outbound(
            row_id=70002,
            phone="+15145551234",
            message="hey John, this is mike from ilowns. we still need this handled.",
        )

        payload = self._payload(event_id="evt-replay-1", row_id=70002, message="i can pay tomorrow")
        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={"answer": "hey John, thanks. total due is $150.00. what time tomorrow?"},
        ), patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended",
            return_value={"status": "success", "sms_log": {"message_id": "sms-2"}},
        ) as mock_send:
            first = self.api_client.post("/api/webhooks/icollector/", payload, format="json")
            second = self.api_client.post("/api/webhooks/icollector/", payload, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get("idempotent_replay"))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(MessagesInbound.objects.filter(row_id=70002).count(), 1)
        self.assertEqual(MessagesOutbound.objects.filter(row_id=70002).count(), 2)  # prior + auto-reply

    def test_missing_prior_outbound_uses_inbound_only_context_and_still_sends(self):
        self._create_crm_and_ingestion(row_id=70003)

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={
                "answer": "Please remit payment to resolve your current balance.",
                "model": "collections-gateway",
            },
        ) as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended",
            return_value={"status": "success", "sms_log": {"message_id": "sms-3"}},
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._payload(event_id="evt-no-prior-1", row_id=70003, message="what do i owe"),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_send.call_count, 1)
        prompt = mock_generate.call_args.kwargs["prompt"]
        self.assertIn("No previous outbound message found.", prompt)

        outbound = MessagesOutbound.objects.filter(row_id=70003).order_by("-id").first()
        self.assertIsNotNone(outbound)
        self.assertTrue(outbound.message_content.startswith("hey"))

    def test_two_close_inbound_messages_use_correct_latest_pairing(self):
        self._create_crm_and_ingestion(row_id=70004)
        self._create_prior_outbound(
            row_id=70004,
            phone="+15145551234",
            message="hey John, this is mike from ilowns. your payment bounced. can you handle this today?",
        )

        event_one_at = timezone.now() + timedelta(seconds=10)
        event_two_at = timezone.now() + timedelta(seconds=20)

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            side_effect=[
                {
                    "answer": "hey John, got it. total due is $150.00. can you send this by 5pm today?",
                    "model": "collections-gateway",
                },
                {
                    "answer": "hey John, thanks. still open at $150.00. can you confirm payment by 7pm?",
                    "model": "collections-gateway",
                },
            ],
        ) as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended",
            side_effect=[
                {"status": "success", "sms_log": {"message_id": "sms-4"}},
                {"status": "success", "sms_log": {"message_id": "sms-5"}},
            ],
        ):
            self.api_client.post(
                "/api/webhooks/icollector/",
                self._payload(
                    event_id="evt-chain-1",
                    row_id=70004,
                    message="i can send this afternoon",
                    occurred_at=event_one_at,
                ),
                format="json",
            )
            self.api_client.post(
                "/api/webhooks/icollector/",
                self._payload(
                    event_id="evt-chain-2",
                    row_id=70004,
                    message="actually i can do evening",
                    occurred_at=event_two_at,
                ),
                format="json",
            )

        self.assertEqual(mock_generate.call_count, 2)
        second_prompt = mock_generate.call_args_list[1].kwargs["prompt"]
        self.assertIn("hey John, got it. total due is $150.00. can you send this by 5pm today?", second_prompt)
        self.assertIn("actually i can do evening", second_prompt)
