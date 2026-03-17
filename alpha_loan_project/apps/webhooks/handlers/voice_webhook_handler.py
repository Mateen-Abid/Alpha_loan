"""Voice Webhook Handler - Telnyx/Twilio call webhooks"""

from typing import Dict


class VoiceWebhookHandler:
    """Handles voice call webhooks"""
    
    @staticmethod
    def handle_call_completed(payload: Dict) -> Dict:
        """Handle voice call completion by delegating to processor."""
        from apps.webhooks.services.webhook_processor import WebhookProcessor

        return WebhookProcessor.route_webhook("voice", payload)
