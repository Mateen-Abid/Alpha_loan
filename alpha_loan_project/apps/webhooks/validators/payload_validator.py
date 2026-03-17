"""Payload Validator - Webhook payload validation"""

from typing import Dict, Tuple


class PayloadValidator:
    """Validates webhook payload structure and content"""
    
    @staticmethod
    def validate_sms_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate SMS webhook payload"""
        required_fields = ['message']
        
        for field in required_fields:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        if not payload.get('message'):
            return False, "Message cannot be empty"
        if not any([payload.get('row_id'), payload.get('from'), payload.get('phone')]):
            return False, "Missing case identifier: row_id/from/phone"
        
        return True, "Valid"

    @staticmethod
    def validate_email_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate inbound email webhook payload."""
        if not payload.get('body'):
            return False, "Missing required field: body"
        if not any([payload.get('row_id'), payload.get('from'), payload.get('email')]):
            return False, "Missing case identifier: row_id/from/email"
        return True, "Valid"
    
    @staticmethod
    def validate_crm_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate CRM webhook payload"""
        required = ['row_id', 'failed_payment_amount']
        for field in required:
            if field not in payload:
                return False, f"Missing field: {field}"
        return True, "Valid"
    
    @staticmethod
    def validate_voice_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate voice call webhook payload"""
        required_fields = ['call_id']
        
        for field in required_fields:
            if field not in payload:
                return False, f"Missing field: {field}"
        
        return True, "Valid"
