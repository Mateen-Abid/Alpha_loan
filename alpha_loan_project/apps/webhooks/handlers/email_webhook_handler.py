"""Email Webhook Handler - Gmail email reply webhooks"""

from typing import Dict


class EmailWebhookHandler:
    """Handles email webhooks"""
    
    @staticmethod
    def handle_email_received(payload: Dict) -> Dict:
        """Handle inbound email by delegating to the webhook processor."""
        from apps.webhooks.services.webhook_processor import WebhookProcessor

        return WebhookProcessor.route_webhook("email", payload)
