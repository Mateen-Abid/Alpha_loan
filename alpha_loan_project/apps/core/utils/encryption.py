"""Encryption - Encryption utilities for sensitive data"""

from cryptography.fernet import Fernet
import os


class EncryptionUtils:
    """Encryption utilities for sensitive data"""
    
    @staticmethod
    def get_cipher():
        """Get cipher for encryption/decryption"""
        key = os.getenv('ENCRYPTION_KEY')
        if not key:
            raise ValueError("ENCRYPTION_KEY environment variable not set")
        return Fernet(key)
    
    @staticmethod
    def encrypt_value(value: str) -> str:
        """Encrypt a value"""
        cipher = EncryptionUtils.get_cipher()
        return cipher.encrypt(value.encode()).decode()
    
    @staticmethod
    def decrypt_value(encrypted: str) -> str:
        """Decrypt a value"""
        cipher = EncryptionUtils.get_cipher()
        return cipher.decrypt(encrypted.encode()).decode()
