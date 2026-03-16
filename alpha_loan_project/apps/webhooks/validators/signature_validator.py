"""Signature Validator - Webhook signature validation"""

import hmac
import hashlib
import os
from typing import Optional


class SignatureValidator:
    """Validates webhook signatures for security"""
    
    @staticmethod
    def validate_heymarket_signature(payload: str, signature: str) -> bool:
        """
        Validate Heymarket webhook signature.
        
        Args:
            payload: Raw payload body
            signature: X-Signature header
        
        Returns:
            True if signature is valid
        """
        secret = os.getenv('HEYMARKET_WEBHOOK_SECRET')
        if not secret:
            return False
        
        expected_signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    @staticmethod
    def validate_telnyx_signature(body: str, signature: str) -> bool:
        """Validate Telnyx webhook signature"""
        secret = os.getenv('TELNYX_WEBHOOK_SECRET')
        if not secret:
            return False
        
        expected_signature = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
    
    @staticmethod
    def validate_twilio_signature(body: str, signature: str, url: str) -> bool:
        """Validate Twilio webhook signature"""
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        if not auth_token:
            return False
        
        expected_signature = hmac.new(
            auth_token.encode(),
            (url + body).encode(),
            hashlib.sha1
        ).digest()
        
        import base64
        expected_signature_b64 = base64.b64encode(expected_signature).decode()
        
        return hmac.compare_digest(signature, expected_signature_b64)
