"""Signature Validator - Webhook signature validation"""

import hmac
import hashlib
import os
import time
from typing import Optional
from urllib.parse import urlencode


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
    def validate_icollector_signature(
        body: bytes,
        method: str,
        path: str,
        query_params: Optional[dict],
        timestamp: str,
        nonce: str,
        signature: str,
    ) -> bool:
        """
        Validate iCollector gateway webhook signature using canonical format.
        """
        # Per partner contract: outbound secret verifies webhook callbacks from iCollector.
        secret = os.getenv("ICOLLECTOR_OUTBOUND_SECRET", "")
        if not all([secret, timestamp, nonce, signature]):
            return False
        try:
            request_ts = int(timestamp)
        except ValueError:
            return False
        window_seconds = int(os.getenv("ICOLLECTOR_SIGNATURE_WINDOW_SECONDS", "300"))
        now_ts = int(time.time())
        if abs(now_ts - request_ts) > window_seconds:
            return False
        provided_signature = signature
        if signature.startswith("sha256="):
            provided_signature = signature.split("=", 1)[1]

        query_string = f"?{urlencode(query_params, doseq=True)}" if query_params else ""
        path_with_query = f"{path}{query_string}"
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = f"{timestamp}.{nonce}.{method.upper()}.{path_with_query}.{body_hash}"
        expected_signature = hmac.new(
            secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(provided_signature, expected_signature)
    
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
