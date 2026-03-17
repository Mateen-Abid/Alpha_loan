"""SMS Webhook Handler - Compatibility wrapper."""

from typing import Dict

from apps.collections.models import InteractionLedger


class SMSWebhookHandler:
    """Handles SMS webhooks from partner integrations."""

    @staticmethod
    def handle_sms_received(payload: Dict) -> Dict:
        from apps.webhooks.services.webhook_processor import WebhookProcessor

        return WebhookProcessor.route_webhook("sms", payload)

    @staticmethod
    def handle_sms_delivery_status(payload: Dict) -> Dict:
        """Handle delivery status updates by external message id."""
        external_id = payload.get("message_id")
        state = str(payload.get("status", "")).lower()
        interaction = InteractionLedger.objects.filter(external_id=external_id).first()
        if not interaction:
            return {"status": "ignored", "reason": "interaction_not_found"}

        status_map = {
            "delivered": InteractionLedger.InteractionStatus.DELIVERED,
            "failed": InteractionLedger.InteractionStatus.FAILED,
            "read": InteractionLedger.InteractionStatus.READ,
        }
        interaction.status = status_map.get(state, interaction.status)
        interaction.save(update_fields=["status"])
        return {"status": "success"}
