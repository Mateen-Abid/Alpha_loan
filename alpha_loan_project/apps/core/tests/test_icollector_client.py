from unittest.mock import patch

from django.test import SimpleTestCase

from apps.core.integrations import ICollectorClient


class ICollectorClientEmailBodyTests(SimpleTestCase):
    @patch.object(ICollectorClient, "request", return_value={"status": "sent"})
    def test_send_email_converts_plain_text_to_html_paragraphs(self, mock_request):
        client = ICollectorClient()

        client.send_email(
            row_id="12001",
            to_email="client@example.com",
            subject="Payment follow-up",
            body="Dear Client,\n\nLine one\nLine two\n\nRegards,\nilowns Collections Team",
        )

        payload = mock_request.call_args.kwargs["body"]
        self.assertEqual(
            payload["body"],
            "<p>Dear Client,</p><p>Line one<br>Line two</p><p>Regards,<br>ilowns Collections Team</p>",
        )

    @patch.object(ICollectorClient, "request", return_value={"status": "sent"})
    def test_send_email_preserves_existing_html_body(self, mock_request):
        client = ICollectorClient()
        html_body = "<p>Hello...</p><p>Thanks</p>"

        client.send_email(
            row_id="12001",
            to_email="client@example.com",
            subject="Payment follow-up",
            body=html_body,
        )

        payload = mock_request.call_args.kwargs["body"]
        self.assertEqual(payload["body"], html_body)

    @patch.object(ICollectorClient, "request", return_value={"status": "sent"})
    def test_send_email_extended_escapes_plain_text_and_keeps_thread_fields(self, mock_request):
        client = ICollectorClient()

        client.send_email_extended(
            row_id=12001,
            to_email="client@example.com",
            subject="Re: Payment follow-up",
            body="Amount check: 2 < 5 & 3 > 1",
            thread_id="thread-1",
            conversation_id="conv-1",
            in_reply_to="abc@host",
            references=["z@host", "abc@host"],
        )

        payload = mock_request.call_args.kwargs["body"]
        self.assertEqual(payload["body"], "<p>Amount check: 2 &lt; 5 &amp; 3 &gt; 1</p>")
        self.assertEqual(payload["thread_id"], "thread-1")
        self.assertEqual(payload["conversation_id"], "conv-1")
        self.assertEqual(payload["in_reply_to"], "abc@host")
