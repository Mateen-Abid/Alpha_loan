"""Telnyx Client - Voice API integration"""

import os
import requests
from typing import Optional, Dict


class TelnyxClient:
    """
    Client for Telnyx Voice API.
    Handles voice calls and voicemail.
    """
    
    def __init__(self):
        self.api_key = os.getenv('TELNYX_API_KEY')
        self.base_url = 'https://api.telnyx.com/v2'
        self.webhook_url = os.getenv('TELNYX_WEBHOOK_URL')
    
    def initiate_call(
        self,
        from_number: str,
        to_number: str,
        script: Optional[str] = None
    ) -> Dict:
        """
        Initiate an outbound call.
        
        Args:
            from_number: Caller ID number
            to_number: Borrower phone number
            script: Optional call script/message
        
        Returns:
            Response with call_id
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'from': from_number,
            'to': to_number,
        }
        
        if script:
            payload['script'] = script
        
        try:
            response = requests.post(
                f'{self.base_url}/calls',
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e), 'status': 'failed'}
    
    def get_call_status(self, call_id: str) -> Dict:
        """Get call status"""
        headers = {'Authorization': f'Bearer {self.api_key}'}
        
        try:
            response = requests.get(
                f'{self.base_url}/calls/{call_id}',
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
