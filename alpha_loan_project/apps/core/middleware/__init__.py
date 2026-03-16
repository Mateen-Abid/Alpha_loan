"""Middleware - Custom middleware"""

import logging

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """Middleware for logging all requests"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Log incoming request
        logger.debug(f"Request: {request.method} {request.path}")
        
        response = self.get_response(request)
        
        # Log outgoing response
        logger.debug(f"Response: {response.status_code}")
        
        return response
