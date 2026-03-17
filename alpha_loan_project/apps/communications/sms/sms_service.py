"""SMS Service - iCollector-backed SMS operations."""

from __future__ import annotations

import logging
from typing import Any, Dict

from apps.core.integrations import ICollectorClient, ICollectorClientError


logger = logging.getLogger(__name__)


class SMSService:
    """Service layer for SMS operations."""

    def __init__(self) -> None:
        self.client = ICollectorClient()

    def send_collection_sms(
        self,
        row_id: str,
        phone_number: str,
        message: str,
    ) -> Dict[str, Any]:
        """Send collection SMS through iCollector partner gateway."""
        try:
            response = self.client.send_sms(row_id=row_id, phone=phone_number, message=message)
            return {
                "status": "success",
                "message_id": response.get("message_id") or response.get("id"),
                "external_id": response.get("message_id") or response.get("id"),
                "provider_response": response,
            }
        except ICollectorClientError as exc:
            logger.error("SMS dispatch failed for row_id=%s: %s", row_id, exc)
            return {"status": "failed", "error": str(exc)}
