"""SMS Service - High-level SMS operations"""

from .heymarket_client import HeymarketClient


class SMSService:
    """Service layer for SMS operations"""
    
    def __init__(self):
        self.client = HeymarketClient()
    
    def send_collection_sms(
        self,
        phone_number: str,
        message: str,
        case_id: str = None
    ) -> Dict:
        """
        Send collection SMS to borrower.
        
        Args:
            phone_number: Borrower phone
            message: SMS message
            case_id: Collection case ID for tracking
        
        Returns:
            Response with external_id
        """
        result = self.client.send_sms(phone_number, message)
        result['case_id'] = case_id
        return result
    
    def send_courtesy_reminder(self, phone_number: str, case_id: str = None) -> Dict:
        """Send courtesy payment reminder"""
        message = "Hello, this is a courtesy reminder about your pending payment."
        return self.send_collection_sms(phone_number, message, case_id)
    
    def send_urgency_message(self, phone_number: str, case_id: str = None) -> Dict:
        """Send urgent payment request"""
        message = "Your account requires immediate attention. Please contact us today."
        return self.send_collection_sms(phone_number, message, case_id)
