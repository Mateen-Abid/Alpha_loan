"""AI App Tests."""

from django.test import TestCase

from apps.ai.constants import build_openai_email_prompt


class AITests(TestCase):
    """Tests for AI prompt builders."""

    def test_initial_email_template_has_paragraph_spacing_and_signoff(self):
        message = build_openai_email_prompt(
            {
                "borrower_name": "Mateen Abid",
                "tenant": "ilowns",
                "stop_payment_deadline": "2pm EST today",
            }
        )
        self.assertTrue(message.startswith("Dear Mateen,\r\n\r\n"))
        self.assertIn("\r\n\r\nPlease call us by 2pm EST today", message)
        self.assertIn("\r\n\r\nRegards,\r\nilowns Collections Team", message)

    def test_initial_email_template_falls_back_to_client_for_noisy_name(self):
        message = build_openai_email_prompt(
            {
                "borrower_name": "This is a test",
                "tenant": "ilowns",
            }
        )
        self.assertTrue(message.startswith("Dear Client,\r\n\r\n"))

    def test_initial_email_template_uses_default_deadline_when_missing(self):
        message = build_openai_email_prompt(
            {
                "borrower_name": "John",
                "tenant": "ilowns",
            }
        )
        self.assertIn("Please call us by 2pm EST today", message)
