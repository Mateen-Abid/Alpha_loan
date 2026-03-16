"""Payload Validator - Webhook payload validation"""

from typing import Dict, Tuple


class PayloadValidator:
    """Validates webhook payload structure and content"""
    
    @staticmethod
    def validate_sms_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate SMS webhook payload"""
        required_fields = ['from', 'message', 'message_id']
        
        for field in required_fields:
            if field not in payload:
                return False, f"Missing required field: {field}"
        
        if not payload.get('message'):
            return False, "Message cannot be empty"
        
        return True, "Valid"
    
    @staticmethod
    def validate_crm_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate CRM webhook payload"""
        if payload.get('event_type') == 'payment':
            required = ['account_id', 'amount', 'date']
            for field in required:
                if field not in payload:
                    return False, f"Missing field: {field}"
        
        return True, "Valid"
    
    @staticmethod
    def validate_voice_webhook(payload: Dict) -> Tuple[bool, str]:
        """Validate voice call webhook payload"""
        required_fields = ['call_id', 'to']
        
        for field in required_fields:
            if field not in payload:
                return False, f"Missing field: {field}"
        
        return True, "Valid"
