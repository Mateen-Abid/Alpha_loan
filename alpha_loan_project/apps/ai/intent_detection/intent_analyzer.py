"""Intent Analyzer - AI-powered intent detection"""

from . import BorrowerIntent
from apps.ai.clients import OpenAIClient
from apps.ai.constants import (
    OPENAI_INTENT_ANALYZER_SYSTEM_PROMPT,
    build_openai_intent_user_prompt,
)
from typing import Dict, Optional


class IntentAnalyzer:
    """Analyzes borrower messages to detect intent"""
    
    def __init__(self):
        self.client = OpenAIClient()
    
    def analyze_message(self, message: str, case_context: Optional[Dict[str, object]] = None) -> Dict:
        """
        Analyze borrower message for intent.
        
        Args:
            message: Message from borrower
        
        Returns:
            Dict with intent, confidence, and summary
        """
        prompt = build_openai_intent_user_prompt(message, case_context=case_context)
        
        response = self.client.call_api(
            prompt=prompt,
            system=OPENAI_INTENT_ANALYZER_SYSTEM_PROMPT,
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
