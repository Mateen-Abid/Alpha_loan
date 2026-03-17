"""iCollector Partner Gateway API client with HMAC request signing."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import logging
import os
import secrets
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests


logger = logging.getLogger(__name__)


class ICollectorClientError(Exception):
    """Raised when iCollector partner gateway returns an error."""


@dataclass(frozen=True)
class _SignedRequest:
    """Container for signed request components."""

    timestamp: str
    nonce: str
    body_hash: str
    canonical: str
    signature: str


class ICollectorClient:
    """Reusable API client for iCollector Partner Gateway."""

    DEFAULT_TIMEOUT = 15

    def __init__(self) -> None:
        self.base_url = os.getenv("ICOLLECTOR_BASE_URL", "https://app.icollector.ai").rstrip("/")
        self.api_token = os.getenv("ICOLLECTOR_API_TOKEN", os.getenv("ICOLLECTOR_API_KEY", ""))
        self.tenant = os.getenv("ICOLLECTOR_TENANT", "")
        # Per partner contract: inbound secret signs partner requests to iCollector.
        self.inbound_secret = os.getenv("ICOLLECTOR_INBOUND_SECRET", "")
        self.session = requests.Session()

    @staticmethod
    def generate_timestamp() -> str:
        """Generate unix timestamp in seconds."""
        return str(int(datetime.now(tz=timezone.utc).timestamp()))

    @staticmethod
    def generate_nonce() -> str:
        """Generate cryptographically secure nonce."""
        return secrets.token_hex(16)

    @staticmethod
    def body_sha256(raw_body: bytes) -> str:
        """Compute SHA256 hex digest of raw request body."""
        return hashlib.sha256(raw_body).hexdigest()

    @classmethod
    def build_canonical_string(
        cls,
        timestamp: str,
        nonce: str,
        method: str,
        path_with_query: str,
        raw_body: bytes,
    ) -> str:
        """Build canonical string for HMAC signature verification."""
        body_hash = cls.body_sha256(raw_body)
        return f"{timestamp}.{nonce}.{method.upper()}.{path_with_query}.{body_hash}"

    @staticmethod
    def compute_signature(secret: str, canonical_string: str) -> str:
        """Generate request signature from canonical payload."""
        return hmac.new(
            secret.encode("utf-8"),
            canonical_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _serialize_body(self, body: Optional[Dict[str, Any]]) -> bytes:
        if body is None:
            return b""
        return json.dumps(body, separators=(",", ":"), ensure_ascii=True).encode("utf-8")

    def _sign_request(
        self,
        method: str,
        path: str,
        raw_body: bytes,
        query: Optional[Dict[str, Any]] = None,
    ) -> _SignedRequest:
        timestamp = self.generate_timestamp()
        nonce = self.generate_nonce()
        query_string = f"?{urlencode(query)}" if query else ""
        path_with_query = f"{path}{query_string}"
        canonical = self.build_canonical_string(timestamp, nonce, method, path_with_query, raw_body)
        signature = self.compute_signature(self.inbound_secret, canonical)
        return _SignedRequest(
            timestamp=timestamp,
            nonce=nonce,
            body_hash=self.body_sha256(raw_body),
            canonical=canonical,
            signature=signature,
        )

    def _headers(self, signed: _SignedRequest) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_token}",
            "X-Tenant": self.tenant,
            "X-Partner-Timestamp": signed.timestamp,
            "X-Partner-Nonce": signed.nonce,
            "X-Partner-Signature": f"sha256={signed.signature}",
        }

    def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> Dict[str, Any]:
        """Send signed HTTP request to iCollector Partner Gateway."""
        if not all([self.api_token, self.tenant, self.inbound_secret]):
            raise ICollectorClientError("iCollector credentials are incomplete")

        raw_body = self._serialize_body(body)
        signed = self._sign_request(method=method, path=path, raw_body=raw_body, query=query)
        url = f"{self.base_url}{path}"

        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                params=query,
                data=raw_body,
                headers=self._headers(signed),
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            logger.exception("iCollector request failed: %s %s", method, path)
            raise ICollectorClientError(str(exc)) from exc

        if not response.content:
            return {"status": "success"}

        try:
            return response.json()
        except ValueError:
            return {"status": "success", "raw": response.text}

    def ping(self) -> Dict[str, Any]:
        return self.request("POST", "/api/partner-gateway/v1/ping/", body={})

    def send_sms(self, row_id: str, phone: str, message: str) -> Dict[str, Any]:
        payload = {"row_id": row_id, "phone": phone, "message": message}
        return self.request("POST", "/api/partner-gateway/v1/sms/send/", body=payload)

    def send_sms_extended(
        self,
        row_id: str,
        phone: str,
        message: str = "",
        media_urls: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"row_id": row_id, "phone": phone}
        if message:
            payload["message"] = message
        if media_urls:
            payload["media_urls"] = media_urls
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return self.request("POST", "/api/partner-gateway/v1/sms/send/", body=payload)

    def send_email(self, row_id: str, to_email: str, subject: str, body: str) -> Dict[str, Any]:
        payload = {
            "row_id": row_id,
            "to_email": to_email,
            "subject": subject,
            "body": body,
        }
        return self.request("POST", "/api/partner-gateway/v1/email/send/", body=payload)

    def send_email_extended(
        self,
        row_id: str,
        to_email: str,
        subject: str,
        body: str,
        mailbox_role: Optional[str] = None,
        connection_id: Optional[int] = None,
        cc: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "row_id": row_id,
            "to_email": to_email,
            "subject": subject,
            "body": body,
        }
        if mailbox_role:
            payload["mailbox_role"] = mailbox_role
        if connection_id is not None:
            payload["connection_id"] = connection_id
        if cc:
            payload["cc"] = cc
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return self.request("POST", "/api/partner-gateway/v1/email/send/", body=payload)

    def get_boards(self) -> Dict[str, Any]:
        return self.request("GET", "/api/partner-gateway/v1/crm/boards/")

    def get_rows(
        self,
        board_id: str,
        limit: int = 100,
        offset: int = 0,
        group_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {"limit": limit, "offset": offset}
        if group_id is not None:
            query["group_id"] = group_id
        return self.request(
            "GET",
            f"/api/partner-gateway/v1/crm/board/{board_id}/rows/",
            query=query,
        )

    def ingest_row(
        self,
        board_id: str,
        group: str,
        data: Dict[str, Any],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"group": group, "data": data}
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return self.request(
            "POST",
            f"/api/partner-gateway/v1/crm/board/{board_id}/ingest/",
            body=payload,
        )

    def update_row(self, row_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        payload: Dict[str, Any]
        if "data" in data:
            payload = data
        else:
            payload = {"data": data}
        return self.request(
            "PATCH",
            f"/api/partner-gateway/v1/crm/row/{row_id}/update/",
            body=payload,
        )

    def move_row(
        self,
        row_id: str,
        target_board_id: str,
        target_group_id: str,
        action_value: Optional[str] = None,
        action_column_title: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "target_board_id": target_board_id,
            "target_group_id": target_group_id,
        }
        if action_value:
            payload["action_value"] = action_value
        if action_column_title:
            payload["action_column_title"] = action_column_title
        if idempotency_key:
            payload["idempotency_key"] = idempotency_key
        return self.request(
            "POST",
            f"/api/partner-gateway/v1/crm/row/{row_id}/move/",
            body=payload,
        )

