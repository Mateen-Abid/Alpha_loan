"""Message Generator - AI-powered response generation"""

from apps.ai.clients import OpenAIClient
from apps.ai.constants import (
    build_openai_email_prompt,
    build_openai_sms_prompt,
    get_openai_email_system_prompt,
    get_openai_sms_system_prompt,
)
from typing import Dict


class MessageGenerator:
    """Generates AI-powered collection messages"""
    
    def __init__(self):
        self.client = OpenAIClient()
    
    def generate_sms(self, context: Dict) -> Dict:
        """
        Generate SMS message for borrower.
        
        Args:
            context: Dict with case info (amount, workflow_step, etc.)
        
        Returns:
            Dict with generated message
        """
        prompt = build_openai_sms_prompt(context)
        workflow_step = context.get('workflow_step', 'STEP_1')
        
        response = self.client.call_api(
            prompt=prompt,
            system=get_openai_sms_system_prompt(workflow_step),
            temperature=0.5
        )
        
        return {
            'message': response.get('content', '') if response.get('status') == 'success' else '',
            'status': response.get('status'),
            'error': response.get('error')
        }
    
    def generate_email(self, context: Dict) -> Dict:
        """Generate email message for borrower"""
        prompt = build_openai_email_prompt(context)
        workflow_step = context.get('workflow_step', 'STEP_1')
        
        response = self.client.call_api(
            prompt=prompt,
            system=get_openai_email_system_prompt(workflow_step),
            temperature=0.5
        )
        
        return {
            'subject': 'Collection Notice',
            'body': response.get('content', '') if response.get('status') == 'success' else '',
            'status': response.get('status'),
            'error': response.get('error')
        }
