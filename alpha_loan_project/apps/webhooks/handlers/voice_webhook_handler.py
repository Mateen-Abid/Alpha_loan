"""Voice Webhook Handler - Telnyx/Twilio call webhooks"""

from typing import Dict


class VoiceWebhookHandler:
    """Handles voice call webhooks"""
    
    @staticmethod
    def handle_call_completed(payload: Dict) -> Dict:
        """
        Handle completed voice call.
        
        Args:
            payload: Webhook payload with call details
        
        Returns:
            Processing result
        """
        try:
            call_id = payload.get('call_id')
            to_number = payload.get('to')
            duration = payload.get('duration')
            transcript = payload.get('transcript')
            
            from apps.collections.services.collection_service import CollectionService
            from apps.collections.models import CollectionCase
            
            # Find case by phone
            case = CollectionCase.objects.filter(borrower_phone=to_number).first()
            
            if case and transcript:
                interaction = CollectionService.record_interaction(
                    case=case,
                    channel='VOICE',
                    interaction_type='OUTBOUND',
                    message_content=transcript,
                    external_id=call_id
                )
                
                # Queue for AI processing
                from apps.webhooks.services.webhook_processor import WebhookProcessor
                WebhookProcessor.queue_voice_processing(case.id, interaction.id, transcript)
                
                return {'status': 'success', 'interaction_id': interaction.id}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
