"""Intent Types - Classification of borrower intents"""

from enum import Enum


class BorrowerIntent(Enum):
    """Enumeration of borrower intents detected from messages"""
    PROMISE_TO_PAY = 'promise_to_pay'
    REFUSAL = 'refusal'
    REQUEST_INFO = 'request_info'
    DISPUTE = 'dispute'
    HARDSHIP = 'hardship'
    PAYMENT_MADE = 'payment_made'
    CALLBACK_REQUEST = 'callback_request'
    UNKNOWN = 'unknown'
