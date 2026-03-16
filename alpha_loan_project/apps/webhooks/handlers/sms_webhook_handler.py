"""SMS Webhook Handler - Heymarket SMS reply webhooks"""

from typing import Dict
from apps.collections.services.collection_service import CollectionService
from apps.collections.models import CollectionCase


class SMSWebhookHandler:
    """Handles SMS webhooks from Heymarket"""
    
    @staticmethod
    def handle_sms_received(payload: Dict) -> Dict:
        """
        Handle incoming SMS from borrower.
        
        Args:
            payload: Webhook payload with SMS details
        
        Returns:
            Processing result
        """
        try:
            phone_number = payload.get('from')
            message = payload.get('message')
            external_id = payload.get('message_id')
            
            # Find case by phone number
            cases = CollectionService.objects.filter(borrower_phone=phone_number)
            
            results = []
            for case in cases:
                interaction = CollectionService.record_interaction(
                    case=case,
                    channel='SMS',
                    interaction_type='INBOUND',
                    message_content=message,
                    external_id=external_id
                )
                
                # Trigger AI processing of message (async)
                from apps.webhooks.services.webhook_processor import WebhookProcessor
                WebhookProcessor.queue_sms_processing(case.id, interaction.id, message)
                
                results.append({'case_id': case.id, 'interaction_id': interaction.id})
            
            return {
                'status': 'success',
                'processed_cases': len(results)
            }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def handle_sms_delivery_status(payload: Dict) -> Dict:
        """Handle SMS delivery status update"""
        try:
            external_id = payload.get('message_id')
            status = payload.get('status')
            
            # Update interaction status
            from apps.collections.models import InteractionLedger
            interaction = InteractionLedger.objects.filter(external_id=external_id).first()
            
            if interaction:
                status_map = {
                    'delivered': 'DELIVERED',
                    'failed': 'FAILED',
                    'read': 'READ'
                }
                interaction.status = status_map.get(status, interaction.status)
                interaction.save()
                
                return {'status': 'success'}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
