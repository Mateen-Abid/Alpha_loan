"""Webhook Request/Response Serializers"""

from rest_framework import serializers


class SMSWebhookSerializer(serializers.Serializer):
    """SMS Webhook Request Serializer"""
    row_id = serializers.IntegerField(required=False, help_text="CRM row ID")
    from_field = serializers.CharField(required=False, help_text="Sender identifier", source='from')
    phone = serializers.CharField(max_length=20, required=False, help_text="Borrower phone number")
    message = serializers.CharField(help_text="SMS message text")
    message_id = serializers.CharField(max_length=100, help_text="Unique message ID")
    external_id = serializers.CharField(max_length=100, required=False, help_text="Borrower external ID")
    timestamp = serializers.DateTimeField(required=False, help_text="ISO 8601 timestamp")


class EmailWebhookSerializer(serializers.Serializer):
    """Email Webhook Request Serializer"""
    row_id = serializers.IntegerField(required=False, help_text="CRM row ID")
    from_field = serializers.EmailField(required=False, help_text="Sender email", source='from')
    email = serializers.EmailField(required=False, help_text="Borrower email")
    to_email = serializers.EmailField(required=False, help_text="Recipient email address")
    subject = serializers.CharField(max_length=200, help_text="Email subject")
    body = serializers.CharField(help_text="Email body")
    message_id = serializers.CharField(max_length=100, help_text="Unique message ID")
    external_id = serializers.CharField(max_length=100, required=False, help_text="Borrower external ID")
    timestamp = serializers.DateTimeField(required=False, help_text="ISO 8601 timestamp")


class VoiceWebhookSerializer(serializers.Serializer):
    """Voice Webhook Request Serializer"""
    phone = serializers.CharField(max_length=20, help_text="Borrower phone number")
    call_id = serializers.CharField(max_length=100, help_text="Unique call ID")
    transcript = serializers.CharField(required=False, help_text="Call transcript")
    duration = serializers.IntegerField(required=False, help_text="Call duration in seconds")
    external_id = serializers.CharField(max_length=100, required=False, help_text="Borrower external ID")
    timestamp = serializers.DateTimeField(required=False, help_text="ISO 8601 timestamp")


class CRMWebhookSerializer(serializers.Serializer):
    """CRM Webhook Request Serializer"""
    row_id = serializers.IntegerField(help_text="CRM row ID")
    failed_payment_amount = serializers.FloatField(help_text="Amount of failed payment")
    board_id = serializers.IntegerField(required=False, help_text="CRM board ID")
    phone = serializers.CharField(max_length=20, required=False, help_text="Borrower phone")
    email = serializers.EmailField(required=False, help_text="Borrower email")
    event_type = serializers.CharField(max_length=50, required=False, help_text="Event type (created, updated, moved)")
    return_reason = serializers.CharField(max_length=50, required=False, help_text="Return reason e.g. nsf")
    external_id = serializers.CharField(max_length=100, required=False, help_text="Row external ID")


class WebhookResponseSerializer(serializers.Serializer):
    """Webhook Response Serializer"""
    status = serializers.CharField(max_length=20, help_text="success or error")
    case_id = serializers.IntegerField(required=False, help_text="CollectionCase ID if created")
    interaction_id = serializers.IntegerField(required=False, help_text="InteractionLedger ID if created")
    message = serializers.CharField(required=False, help_text="Response message")
    error = serializers.CharField(required=False, help_text="Error message if failed")
