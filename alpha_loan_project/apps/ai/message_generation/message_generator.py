"""Message Generator - AI-powered response generation"""

from apps.ai.clients import OpenAIClient
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
        prompt = self._build_sms_prompt(context)
        
        response = self.client.call_api(
            prompt=prompt,
            system=self._get_sms_system_prompt(context['workflow_step']),
            temperature=0.5
        )
        
        return {
            'message': response.get('content', '') if response.get('status') == 'success' else '',
            'status': response.get('status'),
            'error': response.get('error')
        }
    
    def generate_email(self, context: Dict) -> Dict:
        """Generate email message for borrower"""
        prompt = self._build_email_prompt(context)
        
        response = self.client.call_api(
            prompt=prompt,
            system=self._get_email_system_prompt(context['workflow_step']),
            temperature=0.5
        )
        
        return {
            'subject': 'Collection Notice',
            'body': response.get('content', '') if response.get('status') == 'success' else '',
            'status': response.get('status'),
            'error': response.get('error')
        }
    
    def _build_sms_prompt(self, context: Dict) -> str:
        return f"""Generate a professional SMS collection message:
- Amount due: ${context.get('amount_due', 0)}
- Workflow step: {context.get('workflow_step', 'STEP_1')}
- Account age: {context.get('days_delinquent', 0)} days

Message should be concise (160 chars max) and professional."""
    
    def _build_email_prompt(self, context: Dict) -> str:
        return f"""Generate a professional collection email:
- Amount due: ${context.get('amount_due', 0)}
- Workflow step: {context.get('workflow_step', 'STEP_1')}
- Borrower name: {context.get('borrower_name', 'Valued Client')}

Email should be professional and include action items."""
    
    def _get_sms_system_prompt(self, step: str) -> str:
        messages = {
            'STEP_1': 'Be courteous and professional. This is the initial contact.',
            'STEP_2': 'Be urgent but professional. This is a follow-up.',
            'STEP_3': 'Be firm and direct. Mention NSF fees.',
            'STEP_4': 'Be serious. Emphasize payment is critical.',
            'FINAL_PRESSURE': 'Be final and decisive. Final notice.'
        }
        return messages.get(step, 'Be professional.')
    
    def _get_email_system_prompt(self, step: str) -> str:
        return f"Write a {step} collection email. Keep it professional but firm."
