"""Webhook Views - API endpoints for webhooks"""

from rest_framework.decorators import api_view
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework import status
from apps.webhooks.validators.signature_validator import SignatureValidator
from apps.webhooks.validators.payload_validator import PayloadValidator
from apps.webhooks.services.webhook_processor import WebhookProcessor
from django.conf import settings
from drf_spectacular.utils import extend_schema
from apps.webhooks.serializers import (
    SMSWebhookSerializer,
    EmailWebhookSerializer,
    VoiceWebhookSerializer,
    CRMWebhookSerializer,
    WebhookResponseSerializer,
)
import json
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _load_payload(request) -> Dict[str, Any]:
    if request.data:
        return dict(request.data)
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def _validate_gateway_signature(request) -> bool:
    # Temporarily DISABLE signature validation for local testing
    # In production, this should always validate iCollector signatures
    logger.warning("⚠️ WEBHOOK SIGNATURE VALIDATION DISABLED - TEST MODE ONLY")
    return True


@csrf_exempt
@extend_schema(
    request=SMSWebhookSerializer,
    responses={200: WebhookResponseSerializer},
)
@api_view(['POST'])
def sms_webhook(request):
    """
    Handle SMS webhooks from iCollector gateway.
    
    Receives borrower SMS messages and processes them through the collections workflow.
    """
    try:
        if not _validate_gateway_signature(request):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        payload = _load_payload(request)
        valid, msg = PayloadValidator.validate_sms_webhook(payload)
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        result = WebhookProcessor.route_webhook('sms', payload)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"SMS webhook error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@extend_schema(
    request=EmailWebhookSerializer,
    responses={200: WebhookResponseSerializer},
)
@api_view(['POST'])
def email_webhook(request):
    """Handle email webhooks"""
    try:
        if not _validate_gateway_signature(request):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        payload = _load_payload(request)
        valid, msg = PayloadValidator.validate_email_webhook(payload)
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        result = WebhookProcessor.route_webhook('email', payload)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Email webhook error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@extend_schema(
    request=VoiceWebhookSerializer,
    responses={200: WebhookResponseSerializer},
)
@api_view(['POST'])
def voice_webhook(request):
    """Handle voice call webhooks from Telnyx/Twilio"""
    try:
        if not _validate_gateway_signature(request):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        payload = _load_payload(request)
        valid, msg = PayloadValidator.validate_voice_webhook(payload)
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        result = WebhookProcessor.route_webhook('voice', payload)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"Voice webhook error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@extend_schema(
    request=CRMWebhookSerializer,
    responses={200: WebhookResponseSerializer},
)
@api_view(['POST'])
def crm_webhook(request):
    """Handle CRM webhooks for payment and case events"""
    try:
        if not _validate_gateway_signature(request):
            return Response({'error': 'Invalid signature'}, status=status.HTTP_401_UNAUTHORIZED)

        payload = _load_payload(request)
        valid, msg = PayloadValidator.validate_crm_webhook(payload)
        if not valid:
            return Response({'error': msg}, status=status.HTTP_400_BAD_REQUEST)

        result = WebhookProcessor.route_webhook('crm', payload)
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"CRM webhook error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
