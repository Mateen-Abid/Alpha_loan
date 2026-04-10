from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.collections.models import CRMData, IngestionData, MessagesInbound, MessagesOutbound
from apps.core.integrations import ICollectorClientError
from apps.core.views import webhook_handler


@override_settings(ICOLLECTOR_OUTBOUND_SECRET="", AUTO_REPLY_MODE="all")
class ICollectorWebhookAutoReplyTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        webhook_handler._processed_events.clear()
        orch = patch(
            "apps.tasks.followup_tasks.AIOrchestrator.process_borrower_message",
            return_value={
                "intent": {"intent": "unknown", "confidence": 0.5},
                "suggested_response": {"message": ""},
            },
        )
        orch.start()
        self.addCleanup(orch.stop)

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
        self._create_prior_outbound(
            row_id=70001,
            phone="+15145551234",
            message="hey John, this is mike from ilowns. your payment bounced. can you send it today?",
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended",
            return_value={"status": "success", "sms_log": {"message_id": "sms-1"}},
        ) as mock_send:
            response = self.api_client.post("/api/webhooks/icollector/", self._payload(
                event_id="evt-pair-1",
                row_id=70001,
                message="what exactly do i owe right now?",
            ), format="json")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(body["result"]["auto_reply"].get("flow"), "daily_reject_case")
        self.assertEqual(mock_send.call_count, 1)

        inbound = MessagesInbound.objects.get(row_id=70001)
        self.assertTrue(inbound.is_processed)
        self.assertIsNotNone(inbound.processed_at)

        latest_outbound = MessagesOutbound.objects.filter(row_id=70001).order_by("-id").first()
        self.assertIsNotNone(latest_outbound)
        self.assertEqual(latest_outbound.status, MessagesOutbound.Status.SENT)
        self.assertIn("Mike from iLoans", latest_outbound.message_content)
        self.assertIn("Interac now", latest_outbound.message_content)

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

        payload = self._payload(event_id="evt-replay-1", row_id=70002, message="what is the deadline?")
        with patch(
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

        outbound = MessagesOutbound.objects.filter(row_id=70003).order_by("-id").first()
        self.assertIsNotNone(outbound)
        self.assertIn("Mike from iLoans", outbound.message_content)

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
            "apps.core.views.webhook_handler.ICollectorClient.send_sms_extended",
            side_effect=[
                {"status": "success", "sms_log": {"message_id": "sms-4"}},
                {"status": "success", "sms_log": {"message_id": "sms-5"}},
            ],
        ) as mock_send:
            self.api_client.post(
                "/api/webhooks/icollector/",
                self._payload(
                    event_id="evt-chain-1",
                    row_id=70004,
                    message="when is this payment due?",
                    occurred_at=event_one_at,
                ),
                format="json",
            )
            self.api_client.post(
                "/api/webhooks/icollector/",
                self._payload(
                    event_id="evt-chain-2",
                    row_id=70004,
                    message="i need until friday to sort this out",
                    occurred_at=event_two_at,
                ),
                format="json",
            )

        self.assertEqual(mock_send.call_count, 2)
        outbounds = list(MessagesOutbound.objects.filter(row_id=70004).order_by("id"))
        self.assertGreaterEqual(len(outbounds), 3)
        last_two = outbounds[-2:]
        self.assertTrue(all("Mike from iLoans" in o.message_content for o in last_two))

    def test_daily_reject_email_inbound_triggers_autoreply_with_message_pair_context(self):
        _, ingestion = self._create_crm_and_ingestion(row_id=72001, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72001,
            email="john@example.com",
            message="John, this is Mike from ilowns. Please confirm your stop-payment status by 2pm EST today.",
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-1"},
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._email_payload(
                    event_id="evt-email-pair-1",
                    row_id=72001,
                    message="what amount should i send today?",
                ),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(mock_send.call_count, 1)

        inbound = MessagesInbound.objects.get(row_id=72001, channel=MessagesInbound.Channel.EMAIL)
        self.assertTrue(inbound.is_processed)
        self.assertIsNotNone(inbound.processed_at)

        latest_outbound = MessagesOutbound.objects.filter(row_id=72001).order_by("-id").first()
        self.assertIsNotNone(latest_outbound)
        self.assertEqual(latest_outbound.channel, MessagesOutbound.Channel.EMAIL)
        self.assertEqual(latest_outbound.status, MessagesOutbound.Status.SENT)
        self.assertEqual(latest_outbound.email, "john@example.com")
        self.assertIn("Mike from iLoans", latest_outbound.message_content)
        self.assertFalse(latest_outbound.message_content.startswith("Dear "))

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
                    "message_id": "AQMkGraphPriorId",
                    "header_message_id": "<prior-1@icollector.ai>",
                    "thread_id": "thread-abc",
                    "conversation_id": "conversation-abc",
                    "mailbox_role": "collections",
                    "connection": 17,
                }
            },
        )

        inbound_graph_message_id = "AQMkInboundGraphId"
        inbound_header_message_id = "<inbound-2@client.example>"
        payload = self._email_payload(
            event_id="evt-email-thread-1",
            row_id=72011,
            message="please confirm how much i should send this evening",
            subject="Account Update",
            extra_data={
                "message_id": inbound_graph_message_id,
                "header_message_id": inbound_header_message_id,
                "thread_id": "thread-abc",
                "conversation_id": "conversation-abc",
                "mailbox_role": "collections",
                "connection_id": 17,
                "references": ["<prior-1@icollector.ai>", "AQMkIgnoreThis"],
            },
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-thread-1"},
        ) as mock_send:
            response = self.api_client.post("/api/webhooks/icollector/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(mock_send.call_count, 1)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["subject"], "Re: Account Update")
        self.assertIsInstance(kwargs["row_id"], int)
        self.assertEqual(kwargs["mailbox_role"], "collections")
        self.assertEqual(kwargs["connection_id"], 17)
        self.assertEqual(kwargs.get("thread_id"), "thread-abc")
        self.assertEqual(kwargs.get("conversation_id"), "conversation-abc")
        self.assertEqual(kwargs.get("in_reply_to"), "inbound-2@client.example")
        self.assertIn("prior-1@icollector.ai", kwargs.get("references", []))
        self.assertIn("inbound-2@client.example", kwargs.get("references", []))
        self.assertNotIn("AQMkIgnoreThis", kwargs.get("references", []))
        self.assertNotIn("threading", kwargs)
        self.assertNotIn("threadId", kwargs)
        self.assertNotIn("in_reply_to_message_id", kwargs)
        self.assertNotIn("conversationId", kwargs)
        self.assertIn("Mike from iLoans", kwargs["body"])
        self.assertFalse(kwargs["body"].startswith("Dear "))

    def test_email_autoreply_uses_allowed_payload_fields_only(self):
        self._create_crm_and_ingestion(row_id=72012, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72012,
            email="john@example.com",
            message="Please confirm when this will be handled.",
            provider_message_id="AQMkPreviousGraphId",
            provider_response={
                "email_log": {
                    "thread_id": "thread-fallback",
                    "conversation_id": "conversation-fallback",
                    "header_message_id": "<prior-2@icollector.ai>",
                    "connection": 19,
                }
            },
        )

        payload = self._email_payload(
            event_id="evt-email-thread-2",
            row_id=72012,
            message="i will update soon",
            subject="Account Update",
            extra_data={
                "message_id": "AQMkInboundGraph2",
                "header_message_id": "<inbound-3@client.example>",
                "thread_id": "thread-fallback",
                "conversation_id": "conversation-fallback",
            },
        )

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-thread-2"},
        ) as mock_send:
            response = self.api_client.post("/api/webhooks/icollector/", payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(mock_send.call_count, 1)
        kwargs = mock_send.call_args.kwargs
        self.assertEqual(kwargs["thread_id"], "thread-fallback")
        self.assertEqual(kwargs["conversation_id"], "conversation-fallback")
        self.assertEqual(kwargs["in_reply_to"], "inbound-3@client.example")
        self.assertIn("prior-2@icollector.ai", kwargs["references"])
        self.assertIn("inbound-3@client.example", kwargs["references"])
        self.assertEqual(kwargs["connection_id"], 19)
        allowed = {
            "row_id",
            "to_email",
            "subject",
            "body",
            "thread_id",
            "conversation_id",
            "in_reply_to",
            "references",
            "connection_id",
            "idempotency_key",
        }
        self.assertTrue(set(kwargs.keys()).issubset(allowed))
        self.assertEqual(set(kwargs.keys()), allowed)
        self.assertFalse(kwargs["body"].startswith("Dear "))

    def test_daily_reject_email_first_message_includes_greeting(self):
        self._create_crm_and_ingestion(row_id=72021, email="john@example.com")

        with patch(
            "apps.core.views.webhook_handler.ICollectorClient.send_email_extended",
            return_value={"status": "success", "message_id": "email-first-1"},
        ) as mock_send:
            response = self.api_client.post(
                "/api/webhooks/icollector/",
                self._email_payload(
                    event_id="evt-email-first-1",
                    row_id=72021,
                    message="what is the current amount i should send?",
                ),
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["result"]["auto_reply"]["status"], "sent")
        self.assertEqual(mock_send.call_count, 1)
        body = mock_send.call_args.kwargs["body"]
        self.assertTrue(body.startswith("Dear "))

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

        payload = self._email_payload(
            event_id="evt-email-replay-1",
            row_id=72003,
            message="what is the balance i need to clear?",
        )
        with patch(
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
            "apps.tasks.followup_tasks.AIOrchestrator.process_borrower_message",
            side_effect=ICollectorClientError("llm unavailable"),
        ) as mock_orch, patch(
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
        self.assertEqual(body["result"]["auto_reply"]["reason"], "case_pipeline_error")
        self.assertEqual(mock_orch.call_count, 1)
        self.assertEqual(mock_send.call_count, 0)

        inbound = MessagesInbound.objects.get(row_id=72004, channel=MessagesInbound.Channel.EMAIL)
        self.assertTrue(inbound.requires_human)
        self.assertIn("Case pipeline error", inbound.human_notes)
        self.assertFalse(inbound.is_processed)

    def test_email_send_failure_flags_human_review(self):
        self._create_crm_and_ingestion(row_id=72005, email="john@example.com")
        self._create_prior_outbound_email(
            row_id=72005,
            email="john@example.com",
            message="John, this is Mike from ilowns. Confirm your next action.",
        )

        with patch(
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
        self.assertEqual(mock_send.call_count, 1)

        inbound = MessagesInbound.objects.get(row_id=72005, channel=MessagesInbound.Channel.EMAIL)
        self.assertTrue(inbound.requires_human)
        self.assertIn("Email send failed", inbound.human_notes)
        self.assertFalse(inbound.is_processed)
