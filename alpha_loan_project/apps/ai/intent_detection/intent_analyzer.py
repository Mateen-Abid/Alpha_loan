"""Intent Analyzer - AI-powered intent detection"""

from .intent_types import BorrowerIntent
from apps.ai.clients import OpenAIClient
from typing import Dict, Tuple


class IntentAnalyzer:
    """Analyzes borrower messages to detect intent"""
    
    SYSTEM_PROMPT = """You are an AI assistant analyzing loan collection communications.
    
Classify the borrower's message into one of these intents:
- promise_to_pay: Borrower commits to pay
- refusal: Borrower refuses to pay
- request_info: Borrower asking for information
- dispute: Borrower disputes the debt
- hardship: Borrower claims financial hardship
- payment_made: Borrower indicates payment was made
- callback_request: Borrower requests callback
- unknown: Cannot determine intent

Respond with JSON: {"intent": "intent_name", "confidence": 0.0-1.0, "summary": "brief summary"}"""
    
    def __init__(self):
        self.client = OpenAIClient()
    
    def analyze_message(self, message: str) -> Dict:
        """
        Analyze borrower message for intent.
        
        Args:
            message: Message from borrower
        
        Returns:
            Dict with intent, confidence, and summary
        """
        prompt = f"Classify this borrower message: {message}"
        
        response = self.client.call_api(
            prompt=prompt,
            system=self.SYSTEM_PROMPT,
            temperature=0.3  # Low randomness for classification
        )
        
        if response.get('status') == 'success':
            try:
                import json
                result = json.loads(response['content'])
                return result
            except json.JSONDecodeError:
                return {
                    'intent': 'unknown',
                    'confidence': 0.0,
                    'summary': response['content']
                }
        
        return {
            'intent': 'unknown',
            'confidence': 0.0,
            'error': response.get('error')
        }
    
    def get_intent_enum(self, intent_str: str) -> BorrowerIntent:
        """Convert intent string to enum"""
        try:
            return BorrowerIntent[intent_str.upper()]
        except KeyError:
            return BorrowerIntent.UNKNOWN
