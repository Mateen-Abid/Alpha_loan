"""Cache Service - Caching utilities"""

from django.core.cache import cache
from typing import Any, Optional


class CacheService:
    """Wrapper for Django cache"""
    
    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Get value from cache"""
        return cache.get(key)
    
    @staticmethod
    def set(key: str, value: Any, timeout: int = 3600):
        """Set value in cache"""
        cache.set(key, value, timeout)
    
    @staticmethod
    def delete(key: str):
        """Delete value from cache"""
        cache.delete(key)
    
    @staticmethod
    def get_or_set(key: str, default_fn, timeout: int = 3600):
        """Get from cache or compute and set"""
        value = cache.get(key)
        if value is None:
            value = default_fn()
            cache.set(key, value, timeout)
        return value
