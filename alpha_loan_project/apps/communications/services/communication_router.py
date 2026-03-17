"""Communication Router - Routes messages to channel services."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from apps.collections.services.collection_service import CollectionService
from apps.communications.email.email_service import EmailService
from apps.communications.sms.sms_service import SMSService
from apps.communications.voice.voice_service import VoiceService


logger = logging.getLogger(__name__)


class ExternalDispatchError(Exception):
    """Raised when an outbound channel dispatch fails."""


class CommunicationRouter:
    """Routes communications to appropriate channel."""

    def __init__(self) -> None:
        self.sms_service = SMSService()
        self.email_service = EmailService()
        self.voice_service = VoiceService()

    def send_message(
        self,
        channel: str,
        payload: Optional[Dict[str, Any]] = None,
        **legacy_kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Route message to the specified channel using payload contract.

        Payload fields:
        - row_id, case_id, phone, email, message, subject
        """
        prepared = self._normalize_payload(payload, legacy_kwargs)
        result: Dict[str, Any]

        if channel == "sms":
            result = self.sms_service.send_collection_sms(
                row_id=prepared.get("row_id") or prepared.get("account_id") or "",
                phone_number=prepared.get("phone", ""),
                message=prepared.get("message", ""),
            )
            interaction_channel = "SMS"
            recipient = prepared.get("phone")
            subject = ""
        elif channel == "email":
            result = self.email_service.send_collection_email(
                row_id=prepared.get("row_id") or prepared.get("account_id") or "",
                to_email=prepared.get("email", ""),
                subject=prepared.get("subject", "Collection Notice"),
                body=prepared.get("message", ""),
            )
            interaction_channel = "EMAIL"
            recipient = prepared.get("email")
            subject = prepared.get("subject", "Collection Notice")
        elif channel == "voice":
            result = self.voice_service.make_collection_call(
                phone_number=prepared.get("phone", ""),
                message=prepared.get("message", ""),
                case_id=prepared.get("case_id"),
            )
            interaction_channel = "VOICE"
            recipient = prepared.get("phone")
            subject = ""
        else:
            raise ValueError(f"Unknown channel: {channel}")

        if result.get("status") == "failed":
            raise ExternalDispatchError(result.get("error", f"{channel} dispatch failed"))

        case = CollectionService.find_case(
            row_id=prepared.get("row_id"),
            case_id=prepared.get("case_id"),
            account_id=prepared.get("account_id"),
            phone=prepared.get("phone"),
            email=prepared.get("email"),
        )

        if case:
            CollectionService.record_interaction(
                case=case,
                channel=interaction_channel,
                interaction_type="OUTBOUND",
                message_content=prepared.get("message", ""),
                external_id=result.get("external_id") or result.get("message_id") or result.get("id"),
                subject=subject,
                status="SENT",
                ai_generated=bool(prepared.get("ai_generated", False)),
            )
        else:
            logger.warning("No case resolved for outbound %s message recipient=%s", channel, recipient)

        return result

    @staticmethod
    def _normalize_payload(
        payload: Optional[Dict[str, Any]],
        legacy_kwargs: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized = dict(payload or {})
        if "account_id" not in normalized and isinstance(normalized.get("case_id"), str):
            normalized["account_id"] = normalized.get("case_id")

        if not payload:
            recipient = legacy_kwargs.get("recipient", "")
            normalized = {
                "message": legacy_kwargs.get("message", ""),
                "case_id": legacy_kwargs.get("case_id"),
                "account_id": legacy_kwargs.get("case_id"),
                "row_id": legacy_kwargs.get("row_id"),
                "subject": legacy_kwargs.get("subject", "Collection Notice"),
            }
            if "@" in str(recipient):
                normalized["email"] = recipient
            else:
                normalized["phone"] = recipient

        return normalized
