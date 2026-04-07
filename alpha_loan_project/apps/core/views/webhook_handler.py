"""Webhook handler for iCollectorAI outbound events."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Optional
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample
from apps.core.integrations import ICollectorClient, ICollectorClientError
from apps.ai.constants import build_openai_email_prompt

from apps.collections.models import (
    MessagesInbound,
    MessagesOutbound,
    CRMData,
    IngestionData,
)

logger = logging.getLogger(__name__)

# Cache processed event IDs to prevent duplicate processing
_processed_events = set()
MAX_CACHED_EVENTS = 10000
DAILY_REJECT_BOARD_ID = 70
DAILY_REJECT_GROUP_ID = 91
_PHONE_DIGITS_RE = re.compile(r"\D")
_PLACEHOLDER_PATTERN = re.compile(r"\[[^\]]+\]")
_CALL_US_PATTERN = re.compile(r"\bcall\s+us\b[^.!?]*[.!?]?", re.IGNORECASE)
_FORMAL_PHRASE_PATTERN = re.compile(r"\b(please remit|to resolve|current balance is)\b", re.IGNORECASE)


def _verify_signature(request) -> bool:
    """
    Verify the webhook signature from iCollectorAI.
    Uses ICOLLECTOR_OUTBOUND_SECRET for verification.
    """
    secret = getattr(settings, 'ICOLLECTOR_OUTBOUND_SECRET', None)
    if not secret:
        logger.warning("ICOLLECTOR_OUTBOUND_SIGNING_SECRET not configured, skipping verification")
        return True  # Allow if not configured (for development)
    
    signature = request.headers.get('X-Partner-Signature', '')
    timestamp = request.headers.get('X-Partner-Timestamp', '')
    nonce = request.headers.get('X-Partner-Nonce', '')
    
    if not all([signature, timestamp, nonce]):
        logger.warning("Missing signature headers")
        return False
    
    # Accept both:
    # - "<hex>"
    # - "sha256=<hex>"
    normalized_signature = signature.strip()
    if normalized_signature.lower().startswith("sha256="):
        normalized_signature = normalized_signature.split("=", 1)[1].strip()

    # Build canonical (contract) string using method/path/query/body_hash.
    body_bytes = request.body or b""
    body_hash = hashlib.sha256(body_bytes).hexdigest()
    query_string = f"?{urlencode(request.GET, doseq=True)}" if request.GET else ""
    path_with_query = f"{request.path}{query_string}"
    contract_canonical = f"{timestamp}.{nonce}.{request.method.upper()}.{path_with_query}.{body_hash}"
    contract_expected = hmac.new(
        secret.encode("utf-8"),
        contract_canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(normalized_signature, contract_expected):
        return True

    # Compatibility fallback: some integrations sign "<timestamp>.<nonce>.<raw_body>".
    legacy_body = body_bytes.decode("utf-8", errors="replace")
    legacy_canonical = f"{timestamp}.{nonce}.{legacy_body}"
    legacy_expected = hmac.new(
        secret.encode("utf-8"),
        legacy_canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(normalized_signature, legacy_expected):
        return True

    logger.warning("Webhook signature mismatch for event=%s path=%s", request.headers.get("X-Partner-Event", ""), request.path)
    return False


def _is_duplicate_event(event_id: str) -> bool:
    """Check if event was already processed (idempotency)."""
    global _processed_events
    
    if event_id in _processed_events:
        return True
    
    # Cleanup if too many cached
    if len(_processed_events) > MAX_CACHED_EVENTS:
        _processed_events = set(list(_processed_events)[-5000:])
    
    _processed_events.add(event_id)
    return False


def _normalize_phone(phone: str) -> str:
    """Normalize phone number for matching."""
    digits = _PHONE_DIGITS_RE.sub("", phone or "")
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1{digits}"
    return phone


def _digits_tail(phone: str, tail: int = 10) -> str:
    digits = _PHONE_DIGITS_RE.sub("", phone or "")
    if len(digits) > tail:
        return digits[-tail:]
    return digits


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _parse_row_id(raw_row_id) -> Optional[int]:
    try:
        if raw_row_id in (None, "", "null"):
            return None
        return int(raw_row_id)
    except (TypeError, ValueError):
        return None


def _parse_occurred_at(raw_timestamp: object) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
        if timezone.is_naive(parsed):
            return timezone.make_aware(parsed)
        return parsed
    except (ValueError, TypeError, AttributeError):
        return timezone.now()


def _safe_decimal(value: object) -> Optional[Decimal]:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _truncate_text(value: object, max_length: int) -> str:
    """Coerce to string and cap length for DB-bound fields."""
    if value is None:
        return ""
    return str(value).strip()[:max_length]


def _extract_decimal_from_mixed(value: object) -> Optional[Decimal]:
    if isinstance(value, dict):
        for key in ("raw", "value", "amount", "text"):
            if key in value:
                parsed = _safe_decimal(value.get(key))
                if parsed is not None:
                    return parsed
        return None
    if isinstance(value, (list, tuple)):
        for item in value:
            parsed = _extract_decimal_from_mixed(item)
            if parsed is not None:
                return parsed
        return None
    return _safe_decimal(value)


def _extract_fee_from_raw_columns(crm_data: CRMData | None) -> Optional[Decimal]:
    if not crm_data:
        return None
    raw_columns = getattr(crm_data, "raw_columns_json", None) or {}
    lower_map = {str(key).strip().lower(): value for key, value in raw_columns.items()}
    for candidate in ("nsf fee", "fee", "fees", "fees 1", "fees 2", "fees 1/2", "service fee", "fee amount"):
        if candidate in lower_map:
            fee = _extract_decimal_from_mixed(lower_map[candidate])
            if fee is not None and fee >= 0:
                return fee
    return None


def _resolve_fee_amount(
    *,
    amount: Optional[Decimal],
    amount_plus_fee: Optional[Decimal],
    crm_data: CRMData | None,
) -> Optional[Decimal]:
    if amount is not None and amount_plus_fee is not None:
        diff = amount_plus_fee - amount
        if diff >= 0:
            return diff.quantize(Decimal("0.01"))

    raw_fee = _extract_fee_from_raw_columns(crm_data)
    if raw_fee is not None:
        return raw_fee

    configured_fee = _safe_decimal(getattr(settings, "COLLECTION_DEFAULT_FEE_AMOUNT", None))
    if configured_fee is not None and configured_fee >= 0:
        return configured_fee
    return None


def _phone_matches_related(normalized_phone: str, related: Dict[str, object]) -> bool:
    """
    Verify the inbound phone is consistent with known related records.

    If no related phone is available, allow processing to continue.
    """
    inbound_tail = _digits_tail(normalized_phone)
    if not inbound_tail:
        return False

    known_phones = []
    crm_data = related.get("crm_data")
    if crm_data:
        known_phones.append(_normalize_phone(getattr(crm_data, "phone_number_raw", "") or ""))
        known_phones.append(_normalize_phone(getattr(crm_data, "phone_number_formatted", "") or ""))

    ingestion_data = related.get("ingestion_data")
    if ingestion_data:
        known_phones.append(_normalize_phone(getattr(ingestion_data, "phone", "") or ""))

    outbound_message = related.get("outbound_message")
    if outbound_message:
        known_phones.append(_normalize_phone(getattr(outbound_message, "phone", "") or ""))

    filtered = [_digits_tail(phone) for phone in known_phones if phone]
    if not filtered:
        return True
    return inbound_tail in filtered


def _is_daily_reject_related(related: Dict[str, object]) -> bool:
    crm_data = related.get("crm_data")
    if not crm_data:
        return False
    try:
        return (
            int(getattr(crm_data, "board_id", 0)) == DAILY_REJECT_BOARD_ID
            and int(getattr(crm_data, "group_id", 0)) == DAILY_REJECT_GROUP_ID
        )
    except (TypeError, ValueError):
        return False


def _find_related_records(phone: str, row_id: int = None, received_at: Optional[datetime] = None):
    """Find related CRM, Ingestion, and Outbound records by row/client and timestamp."""
    resolved_row_id = _parse_row_id(row_id)
    normalized_phone = _normalize_phone(phone or "")
    phone_tail = _digits_tail(normalized_phone)

    crm_data = None
    ingestion_data = None
    outbound_message = None
    borrower_name = None

    # Try to find by row_id first
    if resolved_row_id:
        try:
            crm_data = CRMData.objects.get(row_id=resolved_row_id)
            borrower_name = crm_data.client
        except CRMData.DoesNotExist:
            pass

        try:
            ingestion_data = IngestionData.objects.get(row_id=resolved_row_id)
            if not borrower_name:
                borrower_name = ingestion_data.borrower
        except IngestionData.DoesNotExist:
            pass

    # Try to find by phone if no row_id match
    if not crm_data and phone:
        crm_qs = CRMData.objects.all()
        if phone_tail:
            crm_qs = crm_qs.filter(
                Q(phone_number_raw__icontains=phone_tail)
                | Q(phone_number_formatted__icontains=phone_tail)
            )
        crm_data = crm_qs.first()

        if crm_data:
            borrower_name = crm_data.client
            resolved_row_id = crm_data.row_id
            try:
                ingestion_data = IngestionData.objects.get(row_id=resolved_row_id)
            except IngestionData.DoesNotExist:
                pass

    # Pair with the most recent outbound message for the same row/client chain.
    outbound_qs = MessagesOutbound.objects.all()
    if resolved_row_id:
        outbound_qs = outbound_qs.filter(row_id=resolved_row_id)
    if received_at:
        outbound_qs = outbound_qs.filter(created_at__lte=received_at)

    if phone_tail:
        outbound_by_phone = outbound_qs.filter(phone__icontains=phone_tail).order_by("-sent_at", "-created_at")
        outbound_message = outbound_by_phone.first()

    if not outbound_message and resolved_row_id:
        outbound_message = outbound_qs.order_by("-sent_at", "-created_at").first()

    return {
        "crm_data": crm_data,
        "ingestion_data": ingestion_data,
        "outbound_message": outbound_message,
        "borrower_name": borrower_name,
        "row_id": resolved_row_id,
        "normalized_phone": normalized_phone,
    }


def _find_related_records_email(
    from_email: str,
    row_id: int = None,
    received_at: Optional[datetime] = None,
):
    """Find related records for inbound email using row_id first, then email fallback."""
    resolved_row_id = _parse_row_id(row_id)
    normalized_email = _normalize_email(from_email)

    crm_data = None
    ingestion_data = None
    outbound_message = None
    borrower_name = None

    if resolved_row_id:
        try:
            crm_data = CRMData.objects.get(row_id=resolved_row_id)
            borrower_name = crm_data.client
        except CRMData.DoesNotExist:
            pass

        try:
            ingestion_data = IngestionData.objects.get(row_id=resolved_row_id)
            if not borrower_name:
                borrower_name = ingestion_data.borrower
        except IngestionData.DoesNotExist:
            pass

    if not crm_data and normalized_email:
        crm_data = CRMData.objects.filter(email__iexact=normalized_email).first()
        if crm_data:
            borrower_name = crm_data.client
            resolved_row_id = crm_data.row_id
            try:
                ingestion_data = IngestionData.objects.get(row_id=resolved_row_id)
            except IngestionData.DoesNotExist:
                pass

    outbound_qs = MessagesOutbound.objects.all()
    if resolved_row_id:
        outbound_qs = outbound_qs.filter(row_id=resolved_row_id)
    if received_at:
        outbound_qs = outbound_qs.filter(created_at__lte=received_at)

    if normalized_email:
        outbound_by_email = outbound_qs.filter(email__iexact=normalized_email).order_by("-sent_at", "-created_at")
        outbound_message = outbound_by_email.first()

    if not outbound_message and resolved_row_id:
        outbound_message = outbound_qs.order_by("-sent_at", "-created_at").first()

    return {
        "crm_data": crm_data,
        "ingestion_data": ingestion_data,
        "outbound_message": outbound_message,
        "borrower_name": borrower_name,
        "row_id": resolved_row_id,
        "normalized_email": normalized_email,
    }


def _extract_reply_context(related: Dict[str, object]) -> Dict[str, object]:
    ingestion_data = related.get("ingestion_data")
    crm_data = related.get("crm_data")
    borrower_name = (
        related.get("borrower_name")
        or (getattr(ingestion_data, "borrower", None) if ingestion_data else None)
        or (getattr(crm_data, "client", None) if crm_data else None)
        or "Client"
    )
    first_name = str(borrower_name).split()[0] if borrower_name else "Client"

    amount = None
    amount_plus_fee = None
    balance = None
    reason_code = ""
    wave = 1

    if ingestion_data:
        amount = _safe_decimal(getattr(ingestion_data, "amount", None))
        amount_plus_fee = _safe_decimal(getattr(ingestion_data, "amount_plus_fee", None))
        balance = _safe_decimal(getattr(ingestion_data, "balance", None))
        reason_code = str(getattr(ingestion_data, "reason_code", "") or "")
        try:
            wave = max(1, min(4, int(getattr(ingestion_data, "wave", 1))))
        except (TypeError, ValueError):
            wave = 1

    if crm_data:
        amount = amount if amount is not None else _safe_decimal(getattr(crm_data, "amount", None))
        balance = balance if balance is not None else _safe_decimal(getattr(crm_data, "balance", None))
        if not reason_code:
            reason_code = str(getattr(crm_data, "reason", "") or "")
        if not ingestion_data:
            try:
                wave = max(1, min(4, int(float(getattr(crm_data, "wave", 1) or 1))))
            except (TypeError, ValueError):
                wave = 1

    fee_amount = _resolve_fee_amount(
        amount=amount,
        amount_plus_fee=amount_plus_fee,
        crm_data=crm_data,
    )
    if amount_plus_fee is None and amount is not None and fee_amount is not None:
        amount_plus_fee = amount + fee_amount

    return {
        "row_id": related.get("row_id"),
        "borrower_name": borrower_name,
        "first_name": first_name,
        "amount": amount or Decimal("0.00"),
        "amount_plus_fee": amount_plus_fee,
        "fee_amount": fee_amount,
        "balance": balance,
        "reason_code": reason_code or "UNKNOWN",
        "wave": wave,
    }


def _sanitize_reply_message(message: str) -> str:
    cleaned = (message or "").strip()
    cleaned = _PLACEHOLDER_PATTERN.sub("", cleaned)
    cleaned = _CALL_US_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


def _is_contract_compliant(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    if _FORMAL_PHRASE_PATTERN.search(text):
        return False
    if _PLACEHOLDER_PATTERN.search(text):
        return False
    if _CALL_US_PATTERN.search(text):
        return False
    return True


def _is_email_contract_compliant(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if _PLACEHOLDER_PATTERN.search(text):
        return False
    return True


def _build_contract_fallback_message(context: Dict[str, object], inbound_text: str) -> str:
    first_name = context.get("first_name") or "Client"
    amount_plus_fee = _safe_decimal(context.get("amount_plus_fee")) or _safe_decimal(context.get("amount")) or Decimal("0.00")
    lower_inbound = (inbound_text or "").lower()
    if any(token in lower_inbound for token in ("yes", "okay", "ok", "pay", "today", "tomorrow")):
        return (
            f"hey {first_name}, thanks for confirming. total due right now is ${amount_plus_fee:.2f}. "
            "what exact time are you sending it?"
        )
    return (
        f"hey {first_name}, this is mike from ilowns. total due is ${amount_plus_fee:.2f}. "
        "are you taking care of this today, or should i lock tomorrow morning?"
    )


def _build_email_contract_fallback_message(context: Dict[str, object]) -> str:
    tenant_name = _truncate_text(getattr(settings, "ICOLLECTOR_TENANT", "") or "{{tenant}}", 120)
    deadline = _truncate_text(
        getattr(settings, "COLLECTION_EMAIL_STOP_PAYMENT_DEADLINE", "") or "2pm EST today",
        64,
    )
    return build_openai_email_prompt(
        {
            "borrower_name": context.get("borrower_name") or "{{client}}",
            "tenant": tenant_name,
            "stop_payment_deadline": deadline,
        }
    )


def _build_reply_prompt(
    context: Dict[str, object],
    *,
    prior_outbound_message: str,
    inbound_message: str,
) -> str:
    balance = _safe_decimal(context.get("balance"))
    balance_text = f"${balance:.2f}" if balance is not None else "unknown"
    fee_amount = _safe_decimal(context.get("fee_amount"))
    due_target = _safe_decimal(context.get("amount_plus_fee")) or _safe_decimal(context.get("amount")) or Decimal("0.00")
    fee_text = f"${fee_amount:.2f}" if fee_amount is not None else "unknown"
    return (
        "You are Mike from ilowns handling an active collections SMS thread.\n\n"
        f"Borrower: {context.get('borrower_name')}\n"
        f"Reason code: {context.get('reason_code')}\n"
        f"Wave: {context.get('wave')}\n"
        f"Fee amount: {fee_text}\n"
        f"Amount due target (amount + fee when available): ${due_target:.2f}\n"
        f"Balance context only: {balance_text}\n\n"
        "Conversation pair (must use both sides to adjust tone):\n"
        f"1) Last message sent to borrower:\n{prior_outbound_message or 'No previous outbound message found.'}\n\n"
        f"2) Borrower reply received:\n{inbound_message}\n\n"
        "Rules:\n"
        "- Write one SMS reply only.\n"
        "- Keep collections tone controlled, direct, and conversational.\n"
        "- Do not use placeholders.\n"
        "- Do not ask borrower to call us.\n"
        "- Ask for concrete payment action/time.\n"
        "- Respect daily reject context: immediate target is missed amount + fee.\n"
        "Return only final SMS text."
    )


def _build_email_reply_prompt(
    context: Dict[str, object],
    *,
    prior_outbound_message: str,
    inbound_message: str,
) -> str:
    balance = _safe_decimal(context.get("balance"))
    balance_text = f"${balance:.2f}" if balance is not None else "unknown"
    fee_amount = _safe_decimal(context.get("fee_amount"))
    due_target = _safe_decimal(context.get("amount_plus_fee")) or _safe_decimal(context.get("amount")) or Decimal("0.00")
    fee_text = f"${fee_amount:.2f}" if fee_amount is not None else "unknown"
    return (
        "You are Mike from ilowns handling an active collections email thread.\n\n"
        f"Borrower: {context.get('borrower_name')}\n"
        f"Reason code: {context.get('reason_code')}\n"
        f"Wave: {context.get('wave')}\n"
        f"Fee amount: {fee_text}\n"
        f"Amount due target (amount + fee when available): ${due_target:.2f}\n"
        f"Balance context only: {balance_text}\n\n"
        "Conversation pair (must use both sides to adjust tone):\n"
        f"1) Last email sent to borrower:\n{prior_outbound_message or 'No previous outbound message found.'}\n\n"
        f"2) Borrower email reply received:\n{inbound_message}\n\n"
        "Rules:\n"
        "- Write one email body reply only (no subject line).\n"
        "- Keep collections tone controlled, direct, and professional.\n"
        "- Match the borrower's tone while keeping authority.\n"
        "- Keep it concise (2-4 short paragraphs).\n"
        "- Do not use placeholders.\n"
        "- Keep amount references accurate.\n"
        "- Ask for concrete payment action or confirmation time.\n"
        "Return only final email body text."
    )


def _maybe_auto_reply_to_inbound(inbound: MessagesInbound, payload: Dict[str, object], related: Dict[str, object]) -> Dict[str, object]:
    """Auto-generate and send reply for Daily Reject inbound SMS when safely matched."""
    if not _is_daily_reject_related(related):
        return {"status": "skipped", "reason": "out_of_scope"}

    row_id = related.get("row_id")
    if row_id is None:
        inbound.requires_human = True
        inbound.human_notes = "Daily Reject scope matched but row_id missing for safe auto-reply."
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "skipped", "reason": "row_id_missing"}

    normalized_phone = related.get("normalized_phone") or _normalize_phone(inbound.from_phone)
    if not _phone_matches_related(str(normalized_phone or ""), related):
        inbound.requires_human = True
        inbound.human_notes = "Phone mismatch against related client records; auto-reply skipped."
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "skipped", "reason": "phone_mismatch"}

    context = _extract_reply_context(related)
    previous_outbound = related.get("outbound_message")
    prior_message_text = getattr(previous_outbound, "message_content", "") if previous_outbound else ""
    prompt = _build_reply_prompt(
        context,
        prior_outbound_message=prior_message_text,
        inbound_message=inbound.message_content,
    )

    client = ICollectorClient()
    idempotency_prefix = str(payload.get("event_id") or f"inbound-{inbound.id}")[:64]

    try:
        llm_result = client.generate_collection_llm(
            prompt=prompt,
            temperature=0.2,
            max_new_tokens=220,
            idempotency_key=f"reply-gen-{idempotency_prefix}-{inbound.id}"[:120],
        )
    except ICollectorClientError as exc:
        inbound.requires_human = True
        inbound.human_notes = f"LLM generation failed: {exc}"
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "failed", "reason": "llm_error", "error": str(exc)}

    raw_message = llm_result.get("answer") or llm_result.get("raw") or ""
    sanitized = _sanitize_reply_message(raw_message)
    final_message = sanitized if _is_contract_compliant(sanitized) else _build_contract_fallback_message(context, inbound.message_content)

    try:
        send_result = client.send_sms_extended(
            row_id=str(row_id),
            phone=inbound.from_phone,
            message=final_message,
            idempotency_key=f"reply-send-{idempotency_prefix}-{inbound.id}"[:120],
        )
    except ICollectorClientError as exc:
        inbound.requires_human = True
        inbound.human_notes = f"SMS send failed: {exc}"
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "failed", "reason": "send_error", "error": str(exc)}

    outbound = MessagesOutbound.objects.create(
        crm_data=related.get("crm_data"),
        ingestion_data=related.get("ingestion_data"),
        row_id=int(row_id),
        borrower_name=str(context.get("borrower_name") or inbound.borrower_name or "Client"),
        phone=inbound.from_phone,
        channel=MessagesOutbound.Channel.SMS,
        wave=int(context.get("wave") or 1),
        amount=_safe_decimal(context.get("amount")),
        total_due=_safe_decimal(context.get("amount_plus_fee")),
        reason=str(context.get("reason_code") or ""),
        message_content=final_message,
        prompt_used=prompt,
        model=str(llm_result.get("model") or "gateway-collection-llm"),
        status=MessagesOutbound.Status.PENDING,
        provider="icollector",
    )
    outbound.mark_sent(provider_response=send_result)

    ingestion_data = related.get("ingestion_data")
    if ingestion_data:
        ingestion_data.message_generated = True
        ingestion_data.message_sent = True
        ingestion_data.last_message_at = timezone.now()
        ingestion_data.save(update_fields=["message_generated", "message_sent", "last_message_at", "updated_at"])

    inbound.outbound_message = outbound
    inbound.is_processed = True
    inbound.processed_at = timezone.now()
    inbound.requires_human = False
    inbound.human_notes = ""
    inbound.save(
        update_fields=[
            "outbound_message",
            "is_processed",
            "processed_at",
            "requires_human",
            "human_notes",
            "updated_at",
        ]
    )

    return {
        "status": "sent",
        "outbound_id": outbound.id,
        "row_id": row_id,
        "message_preview": final_message[:100],
    }


def _email_matches_related(normalized_email: str, related: Dict[str, object]) -> bool:
    """Verify inbound email is consistent with known related records."""
    if not normalized_email:
        return False

    known_emails = []
    crm_data = related.get("crm_data")
    if crm_data:
        known_emails.append(_normalize_email(getattr(crm_data, "email", "") or ""))

    ingestion_data = related.get("ingestion_data")
    if ingestion_data:
        known_emails.append(_normalize_email(getattr(ingestion_data, "email", "") or ""))

    outbound_message = related.get("outbound_message")
    if outbound_message:
        known_emails.append(_normalize_email(getattr(outbound_message, "email", "") or ""))

    filtered = [email for email in known_emails if email]
    if not filtered:
        return True
    return normalized_email in filtered


def _sanitize_reply_email(message: str) -> str:
    cleaned = (message or "").strip()
    cleaned = _PLACEHOLDER_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def _maybe_auto_reply_to_inbound_email(
    inbound: MessagesInbound,
    payload: Dict[str, object],
    related: Dict[str, object],
) -> Dict[str, object]:
    """Auto-generate and send reply for Daily Reject inbound email when safely matched."""
    if not _is_daily_reject_related(related):
        inbound.human_notes = "Auto-reply skipped: out_of_scope (row not in Daily Reject scope)."
        inbound.save(update_fields=["human_notes", "updated_at"])
        return {"status": "skipped", "reason": "out_of_scope"}

    row_id = related.get("row_id")
    if row_id is None:
        inbound.requires_human = True
        inbound.human_notes = "Daily Reject scope matched but row_id missing for safe email auto-reply."
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "skipped", "reason": "row_id_missing"}

    normalized_email = related.get("normalized_email") or _normalize_email(inbound.from_email)
    if not _email_matches_related(str(normalized_email or ""), related):
        inbound.requires_human = True
        inbound.human_notes = "Email mismatch against related client records; auto-reply skipped."
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "skipped", "reason": "email_mismatch"}

    context = _extract_reply_context(related)
    previous_outbound = related.get("outbound_message")
    prior_message_text = getattr(previous_outbound, "message_content", "") if previous_outbound else ""
    prompt = _build_email_reply_prompt(
        context,
        prior_outbound_message=prior_message_text,
        inbound_message=inbound.message_content,
    )

    client = ICollectorClient()
    idempotency_prefix = str(payload.get("event_id") or f"inbound-email-{inbound.id}")[:64]

    try:
        llm_result = client.generate_collection_llm(
            prompt=prompt,
            temperature=0.2,
            max_new_tokens=320,
            idempotency_key=f"reply-email-gen-{idempotency_prefix}-{inbound.id}"[:120],
        )
    except ICollectorClientError as exc:
        inbound.requires_human = True
        inbound.human_notes = f"Email LLM generation failed: {exc}"
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "failed", "reason": "llm_error", "error": str(exc)}

    raw_message = llm_result.get("answer") or llm_result.get("raw") or ""
    sanitized = _sanitize_reply_email(raw_message)
    final_message = sanitized if _is_email_contract_compliant(sanitized) else _build_email_contract_fallback_message(context)

    recipient_email = (
        normalized_email
        or _normalize_email(getattr(previous_outbound, "email", "") if previous_outbound else "")
        or _normalize_email(getattr(related.get("crm_data"), "email", "") if related.get("crm_data") else "")
        or _normalize_email(getattr(related.get("ingestion_data"), "email", "") if related.get("ingestion_data") else "")
    )
    if not recipient_email:
        inbound.requires_human = True
        inbound.human_notes = "No recipient email found for auto-reply."
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "skipped", "reason": "email_missing"}

    try:
        send_result = client.send_email_extended(
            row_id=str(row_id),
            to_email=recipient_email,
            subject="Account Update",
            body=final_message,
            idempotency_key=f"reply-email-send-{idempotency_prefix}-{inbound.id}"[:120],
        )
    except ICollectorClientError as exc:
        inbound.requires_human = True
        inbound.human_notes = f"Email send failed: {exc}"
        inbound.save(update_fields=["requires_human", "human_notes", "updated_at"])
        return {"status": "failed", "reason": "send_error", "error": str(exc)}

    outbound = MessagesOutbound.objects.create(
        crm_data=related.get("crm_data"),
        ingestion_data=related.get("ingestion_data"),
        row_id=int(row_id),
        borrower_name=str(context.get("borrower_name") or inbound.borrower_name or "Client"),
        email=recipient_email,
        channel=MessagesOutbound.Channel.EMAIL,
        wave=int(context.get("wave") or 1),
        amount=_safe_decimal(context.get("amount")),
        total_due=_safe_decimal(context.get("amount_plus_fee")),
        reason=str(context.get("reason_code") or ""),
        message_content=final_message,
        prompt_used=prompt,
        model=str(llm_result.get("model") or "gateway-collection-llm"),
        status=MessagesOutbound.Status.PENDING,
        provider="icollector",
    )
    outbound.mark_sent(provider_response=send_result)

    ingestion_data = related.get("ingestion_data")
    if ingestion_data:
        ingestion_data.message_generated = True
        ingestion_data.message_sent = True
        ingestion_data.last_message_at = timezone.now()
        ingestion_data.save(update_fields=["message_generated", "message_sent", "last_message_at", "updated_at"])

    inbound.outbound_message = outbound
    inbound.is_processed = True
    inbound.processed_at = timezone.now()
    inbound.requires_human = False
    inbound.human_notes = ""
    inbound.save(
        update_fields=[
            "outbound_message",
            "is_processed",
            "processed_at",
            "requires_human",
            "human_notes",
            "updated_at",
        ]
    )

    return {
        "status": "sent",
        "outbound_id": outbound.id,
        "row_id": row_id,
        "message_preview": final_message[:100],
    }


def _handle_sms_received(payload: dict) -> dict:
    """
    Handle sms.received event.
    Save the incoming message to messages_inbound table.
    """
    data = payload.get('data', {})
    
    # Extract message details from payload
    from_phone = data.get('from_phone') or data.get('from') or data.get('phone', '')
    message_content = data.get('message') or data.get('body') or data.get('text', '')
    row_id = _parse_row_id(data.get("row_id"))
    provider_message_id = _truncate_text(data.get('message_id') or data.get('sms_id'), 100)

    # Parse received_at timestamp
    received_at = _parse_occurred_at(payload.get("occurred_at"))

    # Find related records
    related = _find_related_records(from_phone, row_id, received_at=received_at)
    
    # Create inbound message record
    inbound = MessagesInbound.objects.create(
        outbound_message=related['outbound_message'],
        crm_data=related['crm_data'],
        ingestion_data=related['ingestion_data'],
        row_id=related['row_id'] or row_id,
        from_phone=_truncate_text(related["normalized_phone"] or _normalize_phone(from_phone), 50),
        borrower_name=related['borrower_name'],
        channel=MessagesInbound.Channel.SMS,
        message_content=message_content,
        provider='icollector',
        provider_message_id=provider_message_id,
        webhook_payload=payload,
        intent=MessagesInbound.IntentType.NONE,
        is_processed=False,
        received_at=received_at,
    )

    logger.info(f"Saved inbound SMS: id={inbound.id}, from={from_phone}, row_id={related['row_id'] or row_id}")

    auto_reply_result = _maybe_auto_reply_to_inbound(inbound=inbound, payload=payload, related=related)

    return {
        'inbound_id': inbound.id,
        'from_phone': from_phone,
        'row_id': related['row_id'] or row_id,
        'message_preview': message_content[:100] if message_content else '',
        'auto_reply': auto_reply_result,
    }


def _handle_email_received(payload: dict) -> dict:
    """
    Handle email.received event.
    Save the incoming email to messages_inbound table.
    """
    data = payload.get('data', {})
    
    from_email = _truncate_text(data.get('from_email') or data.get('from') or data.get('email', ''), 254)
    message_content = (
        data.get('body')
        or data.get('body_text')
        or data.get('message')
        or data.get('text', '')
    )
    row_id = _parse_row_id(data.get("row_id"))
    provider_message_id = _truncate_text(data.get('message_id') or data.get('email_id'), 100)
    
    occurred_at = payload.get("occurred_at")
    received_at = _parse_occurred_at(occurred_at)

    # Find related records by row_id/email
    related = _find_related_records_email(from_email, row_id, received_at=received_at)
    
    inbound = MessagesInbound.objects.create(
        outbound_message=related['outbound_message'],
        crm_data=related['crm_data'],
        ingestion_data=related['ingestion_data'],
        row_id=related['row_id'] or row_id,
        from_phone='',
        from_email=from_email,
        borrower_name=related['borrower_name'],
        channel=MessagesInbound.Channel.EMAIL,
        message_content=message_content,
        provider='icollector',
        provider_message_id=provider_message_id,
        webhook_payload=payload,
        intent=MessagesInbound.IntentType.NONE,
        is_processed=False,
        received_at=received_at,
    )
    
    logger.info(f"Saved inbound email: id={inbound.id}, from={from_email}, row_id={related['row_id'] or row_id}")

    auto_reply_result = _maybe_auto_reply_to_inbound_email(inbound=inbound, payload=payload, related=related)
    
    return {
        'inbound_id': inbound.id,
        'from_email': from_email,
        'row_id': related['row_id'] or row_id,
        'message_preview': message_content[:100] if message_content else '',
        'auto_reply': auto_reply_result,
    }


@extend_schema(
    summary="iCollectorAI Webhook Endpoint",
    description="""
    Receives outbound webhook events from iCollectorAI.
    
    **Supported Events:**
    - `sms.received`: Client SMS replies → saved to messages_inbound
    - `email.received`: Client email replies → saved to messages_inbound
    - `sms.sent`: Delivery confirmation
    - `email.sent`: Delivery confirmation
    - `crm.row.created`, `crm.row.updated`: CRM sync events
    
    **Headers Required:**
    - `X-Partner-Signature`: HMAC signature
    - `X-Partner-Timestamp`: ISO timestamp
    - `X-Partner-Nonce`: Unique nonce
    - `X-Partner-Event`: Event type
    """,
    request={
        "application/json": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "example": "f0e49ce9-8a95-4fa3-95e1-8f013c62f65e"},
                "event": {"type": "string", "example": "sms.received"},
                "occurred_at": {"type": "string", "example": "2026-03-17T04:30:00.000000+00:00"},
                "source": {"type": "string", "example": "iCollectorAI"},
                "tenant": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "slug": {"type": "string"},
                        "name": {"type": "string"}
                    }
                },
                "data": {
                    "type": "object",
                    "properties": {
                        "from_phone": {"type": "string", "example": "+15145551234"},
                        "message": {"type": "string", "example": "I will pay tomorrow"},
                        "row_id": {"type": "integer", "example": 256028}
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Webhook processed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "event_id": "f0e49ce9-8a95-4fa3-95e1-8f013c62f65e",
                        "event_type": "sms.received",
                        "result": {
                            "inbound_id": 1,
                            "from_phone": "+15145551234",
                            "row_id": 256028
                        }
                    }
                }
            }
        },
        401: {"description": "Invalid signature"},
        400: {"description": "Invalid JSON payload"}
    },
    tags=["Webhooks"]
)
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def icollector_webhook(request):
    """
    Webhook endpoint for iCollectorAI outbound events.
    
    Handles:
    - sms.received: Client SMS replies → messages_inbound
    - email.received: Client email replies → messages_inbound
    
    URL: /api/webhooks/icollector/
    """
    # Verify signature
    if not _verify_signature(request):
        logger.warning("Webhook signature verification failed")
        return Response({
            'status': 'error',
            'code': 'invalid_signature',
            'detail': 'Signature verification failed',
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    # Get payload from DRF request
    payload = request.data
    
    if not payload:
        return Response({
            'status': 'error',
            'code': 'invalid_json',
            'detail': 'Invalid JSON payload',
        }, status=status.HTTP_400_BAD_REQUEST)
    
    event_id = payload.get('event_id', '')
    event_type = payload.get('event', '')
    
    logger.info(f"Received webhook: event_type={event_type}, event_id={event_id}")
    
    # Check idempotency
    if event_id and _is_duplicate_event(event_id):
        logger.info(f"Duplicate event ignored: {event_id}")
        return Response({
            'status': 'success',
            'idempotent_replay': True,
            'detail': 'Event already processed',
        })
    
    # Route by event type
    result = {}
    
    if event_type == 'sms.received':
        result = _handle_sms_received(payload)
    
    elif event_type == 'email.received':
        result = _handle_email_received(payload)
    
    elif event_type in ('sms.sent', 'email.sent'):
        # Delivery confirmation - can be used to update outbound status
        logger.info(f"Delivery event received: {event_type}")
        result = {'acknowledged': True, 'event_type': event_type}
    
    elif event_type in ('crm.row.created', 'crm.row.updated', 'crm.cell.created', 'crm.cell.updated'):
        # CRM update events - can be used to sync data
        logger.info(f"CRM event received: {event_type}")
        result = {'acknowledged': True, 'event_type': event_type}
    
    else:
        logger.warning(f"Unknown event type: {event_type}")
        result = {'acknowledged': True, 'event_type': event_type, 'warning': 'Unknown event type'}
    
    return Response({
        'status': 'success',
        'event_id': event_id,
        'event_type': event_type,
        'result': result,
    })
