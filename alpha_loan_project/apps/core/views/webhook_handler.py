"""Webhook handler for iCollectorAI outbound events."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiExample

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
    
    # Check timestamp is within acceptable window (5 minutes)
    try:
        ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        now = timezone.now()
        if abs((now - ts).total_seconds()) > 300:
            logger.warning("Timestamp out of window")
            return False
    except (ValueError, TypeError):
        logger.warning("Invalid timestamp format")
        return False
    
    # Build canonical string and verify
    body = request.body.decode('utf-8')
    canonical = f"{timestamp}.{nonce}.{body}"
    
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        canonical.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


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
    import re
    digits = re.sub(r'\D', '', phone or '')
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"+1{digits}"
    return phone


def _find_related_records(phone: str, row_id: int = None):
    """Find related CRM, Ingestion, and Outbound records by phone or row_id."""
    crm_data = None
    ingestion_data = None
    outbound_message = None
    borrower_name = None
    
    # Try to find by row_id first
    if row_id:
        try:
            crm_data = CRMData.objects.get(row_id=row_id)
            borrower_name = crm_data.client
        except CRMData.DoesNotExist:
            pass
        
        try:
            ingestion_data = IngestionData.objects.get(row_id=row_id)
            if not borrower_name:
                borrower_name = ingestion_data.borrower
        except IngestionData.DoesNotExist:
            pass
        
        # Find most recent outbound message for this row
        outbound_message = MessagesOutbound.objects.filter(
            row_id=row_id
        ).order_by('-created_at').first()
    
    # Try to find by phone if no row_id match
    if not crm_data and phone:
        normalized_phone = _normalize_phone(phone)
        crm_data = CRMData.objects.filter(
            phone_number_raw__icontains=normalized_phone[-10:]
        ).first()
        
        if crm_data:
            borrower_name = crm_data.client
            row_id = crm_data.row_id
            
            try:
                ingestion_data = IngestionData.objects.get(row_id=row_id)
            except IngestionData.DoesNotExist:
                pass
    
    if not outbound_message and phone:
        normalized_phone = _normalize_phone(phone)
        outbound_message = MessagesOutbound.objects.filter(
            phone__icontains=normalized_phone[-10:]
        ).order_by('-created_at').first()
    
    return {
        'crm_data': crm_data,
        'ingestion_data': ingestion_data,
        'outbound_message': outbound_message,
        'borrower_name': borrower_name,
        'row_id': row_id,
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
    row_id = data.get('row_id')
    provider_message_id = data.get('message_id') or data.get('sms_id')
    
    # Parse received_at timestamp
    occurred_at = payload.get('occurred_at')
    try:
        received_at = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        received_at = timezone.now()
    
    # Find related records
    related = _find_related_records(from_phone, row_id)
    
    # Create inbound message record
    inbound = MessagesInbound.objects.create(
        outbound_message=related['outbound_message'],
        crm_data=related['crm_data'],
        ingestion_data=related['ingestion_data'],
        row_id=related['row_id'] or row_id,
        from_phone=_normalize_phone(from_phone),
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
    
    logger.info(f"Saved inbound SMS: id={inbound.id}, from={from_phone}, row_id={row_id}")
    
    return {
        'inbound_id': inbound.id,
        'from_phone': from_phone,
        'row_id': related['row_id'] or row_id,
        'message_preview': message_content[:100] if message_content else '',
    }


def _handle_email_received(payload: dict) -> dict:
    """
    Handle email.received event.
    Save the incoming email to messages_inbound table.
    """
    data = payload.get('data', {})
    
    from_email = data.get('from_email') or data.get('from') or data.get('email', '')
    message_content = data.get('body') or data.get('message') or data.get('text', '')
    row_id = data.get('row_id')
    provider_message_id = data.get('message_id') or data.get('email_id')
    
    occurred_at = payload.get('occurred_at')
    try:
        received_at = datetime.fromisoformat(occurred_at.replace('Z', '+00:00'))
    except (ValueError, TypeError, AttributeError):
        received_at = timezone.now()
    
    # Find related records by row_id
    related = _find_related_records(None, row_id)
    
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
    
    logger.info(f"Saved inbound email: id={inbound.id}, from={from_email}, row_id={row_id}")
    
    return {
        'inbound_id': inbound.id,
        'from_email': from_email,
        'row_id': related['row_id'] or row_id,
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
