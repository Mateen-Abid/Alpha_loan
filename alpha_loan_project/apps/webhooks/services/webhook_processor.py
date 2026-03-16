"""Webhook Processor - Processes webhooks and queues tasks"""

from typing import Dict


class WebhookProcessor:
    """Processes received webhooks and orchestrates handlers"""
    
    @staticmethod
    def queue_sms_processing(case_id: int, interaction_id: int, message: str):
        """Queue SMS message for AI processing"""
        from apps.tasks.followup_tasks import process_borrowed_message
        
        # Queue async task
        process_borrowed_message.delay(case_id, interaction_id, message)
    
    @staticmethod
    def queue_voice_processing(case_id: int, interaction_id: int, transcript: str):
        """Queue voice call transcript for AI processing"""
        from apps.tasks.followup_tasks import process_voice_transcript
        
        # Queue async task
        process_voice_transcript.delay(case_id, interaction_id, transcript)
    
    @staticmethod
    def route_webhook(webhook_type: str, payload: Dict) -> Dict:
        """
        Route webhook to appropriate handler.
        
        Args:
            webhook_type: Type of webhook (sms, email, voice, crm)
            payload: Webhook payload
        
        Returns:
            Processing result
        """
        if webhook_type == 'sms':
            from apps.webhooks.handlers.sms_webhook_handler import SMSWebhookHandler
            return SMSWebhookHandler.handle_sms_received(payload)
        elif webhook_type == 'email':
            from apps.webhooks.handlers.email_webhook_handler import EmailWebhookHandler
            return EmailWebhookHandler.handle_email_received(payload)
        elif webhook_type == 'voice':
            from apps.webhooks.handlers.voice_webhook_handler import VoiceWebhookHandler
            return VoiceWebhookHandler.handle_call_completed(payload)
        elif webhook_type == 'crm':
            from apps.webhooks.handlers.crm_webhook_handler import CRMWebhookHandler
            return CRMWebhookHandler.handle_payment_webhook(payload)
        else:
            return {'error': f'Unknown webhook type: {webhook_type}'}
