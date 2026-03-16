"""Twilio Client - Alternative voice provider"""

import os
from typing import Optional, Dict


class TwilioClient:
    """
    Client for Twilio Voice API.
    Alternative provider for voice calls.
    """
    
    def __init__(self):
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    def initiate_call(
        self,
        to_number: str,
        url: Optional[str] = None,
        method: str = 'POST'
    ) -> Dict:
        """
        Initiate an outbound call via Twilio.
        
        Args:
            to_number: Borrower phone number
            url: Callback URL for TwiML
            method: HTTP method for callback
        
        Returns:
            Response with call_sid
        """
        try:
            from twilio.rest import Client
            client = Client(self.account_sid, self.auth_token)
            
            call = client.calls.create(
                to=to_number,
                from_=self.from_number,
                url=url,
                method=method
            )
            
            return {'call_sid': call.sid, 'status': 'initiated'}
        except Exception as e:
            return {'error': str(e), 'status': 'failed'}
