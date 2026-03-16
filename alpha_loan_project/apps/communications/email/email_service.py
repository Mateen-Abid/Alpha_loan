"""Email Service - High-level email operations"""

from .gmail_client import GmailClient


class EmailService:
    """Service layer for email operations"""
    
    def __init__(self):
        self.client = GmailClient()
    
    def send_collection_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        case_id: str = None,
        html: bool = False
    ) -> Dict:
        """
        Send collection email to borrower.
        
        Args:
            to_email: Borrower email
            subject: Email subject
            body: Email body
            case_id: Collection case ID for tracking
            html: Whether to send as HTML
        
        Returns:
            Response with external_id
        """
        result = self.client.send_email(to_email, subject, body, html=html)
        result['case_id'] = case_id
        return result
    
    def send_payment_request_email(self, to_email: str, amount: float, case_id: str = None) -> Dict:
        """Send payment request email"""
        subject = "Payment Request - Action Required"
        body = f"""
        Dear Borrower,
        
        This is to request payment of ${amount:.2f} on your account.
        Please arrange payment at your earliest convenience.
        
        Thank you.
        """
        return self.send_collection_email(to_email, subject, body, case_id)
