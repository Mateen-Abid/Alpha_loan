"""Validators - Validation utilities"""

import re
from typing import Tuple


class ValidationUtils:
    """Utility validators for common fields"""
    
    @staticmethod
    def validate_phone(phone: str) -> Tuple[bool, str]:
        """Validate phone number format"""
        # Simple validation - adjust regex based on requirements
        pattern = r'^[\+]?1?[\s.-]?\(?[2-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}$'
        if re.match(pattern, phone):
            return True, "Valid"
        return False, "Invalid phone format"
    
    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if re.match(pattern, email):
            return True, "Valid"
        return False, "Invalid email format"
    
    @staticmethod
    def validate_amount(amount: float) -> Tuple[bool, str]:
        """Validate monetary amount"""
        if amount > 0:
            return True, "Valid"
        return False, "Amount must be positive"
