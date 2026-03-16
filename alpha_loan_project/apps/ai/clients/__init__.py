"""OpenAI Client - GPT API integration"""

import os
import openai
from typing import Dict, Optional


class OpenAIClient:
    """Client for OpenAI API"""
    
    def __init__(self):
        self.api_key = os.getenv('OPENAI_API_KEY')
        openai.api_key = self.api_key
        self.model = os.getenv('OPENAI_MODEL', 'gpt-3.5-turbo')
    
    def call_api(self, prompt: str, system: str = None, temperature: float = 0.7) -> Dict:
        """
        Call OpenAI API.
        
        Args:
            prompt: User message
            system: System prompt
            temperature: Creativity level (0-1)
        
        Returns:
            Response with completion
        """
        try:
            messages = []
            if system:
                messages.append({'role': 'system', 'content': system})
            messages.append({'role': 'user', 'content': prompt})
            
            response = openai.ChatCompletion.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=500
            )
            
            return {
                'content': response.choices[0].message.content,
                'status': 'success'
            }
        except Exception as e:
            return {'error': str(e), 'status': 'failed'}
