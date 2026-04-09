from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.collections.models import CRMData, IngestionData, MessagesInbound, MessagesOutbound
from apps.core.integrations import ICollectorClientError
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
        email: str = "john@example.com",
    ) -> tuple[CRMData, IngestionData]:
        crm = CRMData.objects.create(
            row_id=row_id,
            board_id=board_id,
            group_id=group_id,
            client="John Doe",
            phone_number_raw=phone,
            email=email,
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
            email=email,
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

    def _create_prior_outbound_email(
        self,
        *,
        row_id: int,
        email: str,
        message: str,
        provider_message_id: str = "",
        provider_response=None,
    ) -> MessagesOutbound:
        return MessagesOutbound.objects.create(
            row_id=row_id,
            borrower_name="John Doe",
            email=email,
            channel=MessagesOutbound.Channel.EMAIL,
            wave=1,
            amount=Decimal("100.00"),
            total_due=Decimal("150.00"),
            reason="NSF_1",
            message_content=message,
            status=MessagesOutbound.Status.SENT,
            provider="icollector",
            provider_message_id=provider_message_id or None,
            provider_response=provider_response,
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

    def _email_payload(
        self,
        *,
        event_id: str,
        row_id: int,
        message: str,
        from_email: str = "john@example.com",
        occurred_at=None,
        subject: str = "Account Update",
        extra_data=None,
    ):
        data = {
            "from_email": from_email,
            "body": message,
            "row_id": row_id,
            "message_id": f"provider-email-{event_id}",
            "subject": subject,
        }
        if extra_data:
            data.update(extra_data)
        return {
            "event_id": event_id,
            "event": "email.received",
            "occurred_at": (occurred_at or (timezone.now() + timedelta(seconds=10))).isoformat(),
            "data": data,
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

    def test_daily_reject_email_inbound_triggers_autoreply_with_message_pair_context(self):
        _, ingestion = self._create_crm_and_ingestion(row_id=72001, email="john@example.com")
        prior = self._create_prior_outbound_email(
            row_id=72001,
            email="john@example.com",
            message="John, this is Mike from ilowns. Please confirm your stop-payment status by 2pm EST today.",
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={
                "answer": "John,\n\nThanks for the update. Please confirm the exact time today that you will remove the stop payment.\n\nThank you.",
                "model": "collections-gateway",
            },
        ) as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-1"},
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._email_payload(event_id="evt-email-pair-1", row_id=72001, message="I can call by noon"),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(mock_send.call_count, 1)

        prompt = mock_generate.call_args.kwargs["prompt"]
        self.assertIn(prior.message_content, prompt)
        self.assertIn("I can call by noon", prompt)
        self.assertIn("Amount due target (amount + fee when available): $150.00", prompt)
        self.assertIn("Fee amount: $50.00", prompt)

        inbound = MessagesInbound.objects.get(row_id=72001, channel=MessagesInbound.Channel.EMAIL)
        self.assertTrue(inbound.is_processed)
        self.assertIsNotNone(inbound.processed_at)

        latest_outbound = MessagesOutbound.objects.filter(row_id=72001).order_by("-id").first()
        self.assertIsNotNone(latest_outbound)
        self.assertEqual(latest_outbound.channel, MessagesOutbound.Channel.EMAIL)
        self.assertEqual(latest_outbound.status, MessagesOutbound.Status.SENT)
        self.assertEqual(latest_outbound.email, "john@example.com")

        ingestion.refresh_from_db()
        self.assertTrue(ingestion.message_generated)
        self.assertTrue(ingestion.message_sent)
        self.assertIsNotNone(ingestion.last_message_at)

    def test_daily_reject_email_autoreply_passes_thread_metadata_to_gateway(self):
        self._create_crm_and_ingestion(row_id=72011, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72011,
            email="john@example.com",
            message="John, this is Mike from ilowns. Please confirm your stop-payment status by 2pm EST today.",
            provider_message_id="<prior-1@icollector.ai>",
            provider_response={
                "email_log": {
                    "message_id": "<prior-1@icollector.ai>",
                    "thread_id": "thread-abc",
                    "mailbox_role": "collections",
                    "connection_id": 17,
                }
            },
        )

        inbound_message_id = "<inbound-2@client.example>"
        payload = self._email_payload(
            event_id="evt-email-thread-1",
            row_id=72011,
            message="i can pay this evening",
            subject="Re: Account Update",
            extra_data={
                "message_id": inbound_message_id,
                "thread_id": "thread-abc",
                "mailbox_role": "collections",
                "connection_id": 17,
                "references": ["<prior-1@icollector.ai>"],
            },
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={
                "answer": "John,\n\nPlease confirm the exact payment time this evening.\n\nThank you.",
                "model": "collections-gateway",
            },
        ), patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-thread-1"},
        ) as mock_send:
            response = self.api_client.post("/api/webhooks/icollector/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_send.call_count, 1)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Re: Account Update")
        self.assertEqual(kwargs["mailbox_role"], "collections")
        self.assertEqual(kwargs["connection_id"], 17)
        self.assertIn("threading", kwargs)
        threading = kwargs["threading"]
        self.assertEqual(threading.get("thread_id"), "thread-abc")
        self.assertEqual(threading.get("in_reply_to_message_id"), inbound_message_id)
        self.assertEqual(threading.get("reply_to_message_id"), inbound_message_id)
        self.assertEqual(threading.get("in_reply_to"), inbound_message_id)
        self.assertIn("<prior-1@icollector.ai>", threading.get("references", []))
        self.assertIn(inbound_message_id, threading.get("references", []))

    def test_email_threading_validation_error_retries_with_basic_payload(self):
        self._create_crm_and_ingestion(row_id=72012, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72012,
            email="john@example.com",
            message="Please confirm when this will be handled.",
            provider_message_id="<prior-2@icollector.ai>",
            provider_response={"email_log": {"thread_id": "thread-fallback", "connection_id": 19}},
        )

        payload = self._email_payload(
            event_id="evt-email-thread-2",
            row_id=72012,
            message="i will update soon",
            subject="Re: Account Update",
            extra_data={
                "message_id": "<inbound-3@client.example>",
                "thread_id": "thread-fallback",
                "mailbox_role": "collections",
                "connection_id": 19,
            },
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={"answer": "Please confirm exact timing today.", "model": "collections-gateway"},
        ), patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            side_effect=[
                ICollectorClientError("400 Client Error: Bad Request | detail=Unknown field: thread_id"),
                {"status": "success", "message_id": "email-thread-2"},
            ],
        ) as mock_send:
            response = self.api_client.post("/api/webhooks/icollector/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(mock_send.call_count, 2)
        first_kwargs = mock_send.call_args_list[0].kwargs
        second_kwargs = mock_send.call_args_list[1].kwargs
        self.assertIn("threading", first_kwargs)
        self.assertIn("mailbox_role", first_kwargs)
        self.assertIn("connection_id", first_kwargs)
        self.assertNotIn("threading", second_kwargs)
        self.assertNotIn("mailbox_role", second_kwargs)
        self.assertNotIn("connection_id", second_kwargs)

    def test_non_daily_reject_email_row_stores_inbound_only(self):
        self._create_crm_and_ingestion(row_id=72002, board_id=71, group_id=91, email="john@example.com")

        with patch("apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm") as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended"
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._email_payload(event_id="evt-email-outscope-1", row_id=72002, message="hello from email"),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"]["auto_reply"]["status"], "skipped")
        self.assertEqual(body["result"]["auto_reply"]["reason"], "out_of_scope")
        self.assertEqual(mock_generate.call_count, 0)
        self.assertEqual(mock_send.call_count, 0)
        self.assertEqual(MessagesInbound.objects.filter(channel=MessagesInbound.Channel.EMAIL).count(), 1)

    def test_email_idempotent_replay_does_not_send_duplicate_outbound(self):
        self._create_crm_and_ingestion(row_id=72003, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72003,
            email="john@example.com",
            message="John, this is Mike from ilowns. Please confirm when you can resolve this.",
        )

        payload = self._email_payload(event_id="evt-email-replay-1", row_id=72003, message="I can do this tomorrow")
        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={"answer": "Please confirm exact time tomorrow.", "model": "collections-gateway"},
        ), patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-2"},
        ) as mock_send:
            first = self.api_client.post("/api/webhooks/icollector/", payload, format="json")
            second = self.api_client.post("/api/webhooks/icollector/", payload, format="json")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertTrue(second.json().get("idempotent_replay"))
        self.assertEqual(mock_send.call_count, 1)
        self.assertEqual(
            MessagesInbound.objects.filter(row_id=72003, channel=MessagesInbound.Channel.EMAIL).count(),
            1,
        )
        self.assertEqual(MessagesOutbound.objects.filter(row_id=72003).count(), 2)  # prior + auto-reply

    def test_email_llm_failure_flags_human_review(self):
        self._create_crm_and_ingestion(row_id=72004, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72004,
            email="john@example.com",
            message="John, this is Mike from ilowns. Please confirm stop payment removal by 2pm EST.",
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            side_effect=ICollectorClientError("llm unavailable"),
        ) as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended"
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._email_payload(event_id="evt-email-llm-fail-1", row_id=72004, message="can i do this tomorrow?"),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"]["auto_reply"]["status"], "failed")
        self.assertEqual(body["result"]["auto_reply"]["reason"], "llm_error")
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(mock_send.call_count, 0)

        inbound = MessagesInbound.objects.get(row_id=72004, channel=MessagesInbound.Channel.EMAIL)
        self.assertTrue(inbound.requires_human)
        self.assertIn("Email LLM generation failed", inbound.human_notes)
        self.assertFalse(inbound.is_processed)

    def test_email_send_failure_flags_human_review(self):
        self._create_crm_and_ingestion(row_id=72005, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72005,
            email="john@example.com",
            message="John, this is Mike from ilowns. Confirm your next action.",
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.generate_collection_llm",
            return_value={"answer": "Please confirm exact time today.", "model": "collections-gateway"},
        ) as mock_generate, patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            side_effect=ICollectorClientError("email send failed"),
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._email_payload(event_id="evt-email-send-fail-1", row_id=72005, message="working on it"),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["result"]["auto_reply"]["status"], "failed")
        self.assertEqual(body["result"]["auto_reply"]["reason"], "send_error")
        self.assertEqual(mock_generate.call_count, 1)
        self.assertEqual(mock_send.call_count, 1)

        inbound = MessagesInbound.objects.get(row_id=72005, channel=MessagesInbound.Channel.EMAIL)
        self.assertTrue(inbound.requires_human)
        self.assertIn("Email send failed", inbound.human_notes)
        self.assertFalse(inbound.is_processed)
