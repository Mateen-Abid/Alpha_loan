"""Voice Service - High-level voice operations"""

from .telnyx_client import TelnyxClient
from .twilio_client import TwilioClient


class VoiceService:
    """Service layer for voice operations"""
    
    def __init__(self, provider: str = 'telnyx'):
        if provider == 'twilio':
            self.client = TwilioClient()
        else:
            self.client = TelnyxClient()
        self.provider = provider
    
    def make_collection_call(
        self,
        phone_number: str,
        message: str = None,
        case_id: str = None
    ) -> Dict:
        """
        Initiate collection call to borrower.
        
        Args:
            phone_number: Borrower phone
            message: Optional call script
            case_id: Collection case ID for tracking
        
        Returns:
            Response with call_id
        """
        result = self.client.initiate_call(phone_number, script=message)
        result['case_id'] = case_id
        result['provider'] = self.provider
        return result
