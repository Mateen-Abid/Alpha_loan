"""Database tables for collections app"""

from .crm_data import CRMData
from .ingestion_data import IngestionData
from .messages_outbound import MessagesOutbound
from .messages_inbound import MessagesInbound

__all__ = [
    'CRMData',
    'IngestionData',
    'MessagesOutbound',
    'MessagesInbound',
]
