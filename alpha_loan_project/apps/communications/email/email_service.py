"""Email Service - iCollector-backed email operations."""

from __future__ import annotations

import logging
from typing import Any, Dict

from apps.core.integrations import ICollectorClient, ICollectorClientError


logger = logging.getLogger(__name__)


class EmailService:
    """Service layer for email operations."""

    def __init__(self) -> None:
        self.client = ICollectorClient()

    def send_collection_email(
        self,
        row_id: str,
        to_email: str,
        subject: str,
        body: str,
    ) -> Dict[str, Any]:
        """Send collection email through iCollector partner gateway."""
        try:
            response = self.client.send_email(row_id=row_id, to_email=to_email, subject=subject, body=body)
            return {
                "status": "success",
                "message_id": response.get("message_id") or response.get("id"),
                "external_id": response.get("message_id") or response.get("id"),
                "provider_response": response,
            }
        except ICollectorClientError as exc:
            logger.error("Email dispatch failed for row_id=%s: %s", row_id, exc)
            return {"status": "failed", "error": str(exc)}
