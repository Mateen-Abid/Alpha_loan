"""Communication Router - Routes messages to appropriate channel"""

from apps.communications.sms.sms_service import SMSService
from apps.communications.email.email_service import EmailService
from apps.communications.voice.voice_service import VoiceService
from typing import Dict


class CommunicationRouter:
    """Routes communications to appropriate channel"""
    
    def __init__(self):
        self.sms_service = SMSService()
        self.email_service = EmailService()
        self.voice_service = VoiceService()
    
    def send_message(
        self,
        channel: str,
        recipient: str,
        message: str,
        case_id: str = None
    ) -> Dict:
        """
        Route message to specified channel.
        
        Args:
            channel: 'sms', 'email', or 'voice'
            recipient: Phone number or email
            message: Message content
            case_id: Collection case ID
        
        Returns:
            Response from channel service
        """
        if channel == 'sms':
            return self.sms_service.send_collection_sms(recipient, message, case_id)
        elif channel == 'email':
            return self.email_service.send_collection_email(recipient, 'Collection Notice', message, case_id)
        elif channel == 'voice':
            return self.voice_service.make_collection_call(recipient, message, case_id)
        else:
            return {'error': f'Unknown channel: {channel}'}
