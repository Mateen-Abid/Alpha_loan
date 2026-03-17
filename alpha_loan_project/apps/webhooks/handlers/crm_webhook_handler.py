"""CRM Webhook Handler - Payment and case event webhooks."""

from typing import Dict


class CRMWebhookHandler:
    """Handles webhooks from CRM system"""
    
    @staticmethod
    def handle_payment_webhook(payload: Dict) -> Dict:
        """Handle CRM payment/failed payment webhook."""
        from apps.webhooks.services.webhook_processor import WebhookProcessor

        return WebhookProcessor.route_webhook("crm", payload)
    
    @staticmethod
    def handle_account_update_webhook(payload: Dict) -> Dict:
        """Handle account update webhook"""
        from apps.webhooks.services.webhook_processor import WebhookProcessor

        return WebhookProcessor.route_webhook("crm", payload)
