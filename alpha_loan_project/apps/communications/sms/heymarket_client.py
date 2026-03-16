"""Heymarket Client - SMS API integration"""

import os
import requests
from typing import Optional, Dict


class HeymarketClient:
    """
    Client for Heymarket SMS API.
    Handles SMS sending and webhook management.
    """
    
    def __init__(self):
        self.api_key = os.getenv('HEYMARKET_API_KEY')
        self.base_url = os.getenv('HEYMARKET_BASE_URL', 'https://api.heymarket.io/v1')
        self.webhook_url = os.getenv('HEYMARKET_WEBHOOK_URL')
    
    def send_sms(
        self,
        phone_number: str,
        message: str,
        sender_id: Optional[str] = None
    ) -> Dict:
        """
        Send SMS message via Heymarket.
        
        Args:
            phone_number: Borrower phone number
            message: SMS message content
            sender_id: Optional sender ID
        
        Returns:
            Response with message_id and status
        """
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'to': phone_number,
            'content': message,
        }
        
        if sender_id:
            payload['from'] = sender_id
        
        try:
            response = requests.post(
                f'{self.base_url}/messages',
                json=payload,
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e), 'status': 'failed'}
    
    def register_webhook(self) -> Dict:
        """Register webhook for SMS replies"""
        if not self.webhook_url:
            return {'error': 'Webhook URL not configured'}
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            'url': self.webhook_url,
            'events': ['message.received', 'message.delivered', 'message.failed']
        }
        
        try:
            response = requests.post(
                f'{self.base_url}/webhooks',
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'error': str(e)}
