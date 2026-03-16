"""Decorators - Custom decorators"""

import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def log_action(action_name: str):
    """Decorator to log actions"""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info(f"Starting: {action_name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed: {action_name}")
                return result
            except Exception as e:
                logger.error(f"Failed: {action_name} - {str(e)}")
                raise
        return wrapper
    return decorator


def require_authentication(func: Callable):
    """Decorator to require authentication"""
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden("Authentication required")
        return func(request, *args, **kwargs)
    return wrapper
