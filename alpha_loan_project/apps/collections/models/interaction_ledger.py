"""InteractionLedger Model - Communication log tracking"""

from django.db import models
from .collection_case import CollectionCase


class InteractionLedger(models.Model):
    """
    Records all communication interactions (SMS, Email, Voice calls).
    Provides complete audit trail of borrower communications.
    """
    
    class CommunicationChannel(models.TextChoices):
        SMS = 'SMS', 'SMS/Text'
        EMAIL = 'EMAIL', 'Email'
        VOICE = 'VOICE', 'Voice Call'
        MANUAL = 'MANUAL', 'Manual Contact'
    
    class InteractionStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SENT = 'SENT', 'Sent'
        DELIVERED = 'DELIVERED', 'Delivered'
        READ = 'READ', 'Read'
        REPLIED = 'REPLIED', 'Replied'
        FAILED = 'FAILED', 'Failed'
        BOUNCED = 'BOUNCED', 'Bounced'
    
    class InteractionType(models.TextChoices):
        OUTBOUND = 'OUTBOUND', 'Outbound'
        INBOUND = 'INBOUND', 'Inbound'
    
    collection_case = models.ForeignKey(
        CollectionCase,
        on_delete=models.CASCADE,
        related_name='interactions'
    )
    
    channel = models.CharField(
        max_length=20,
        choices=CommunicationChannel.choices,
        db_index=True
    )
    
    interaction_type = models.CharField(
        max_length=20,
        choices=InteractionType.choices,
        db_index=True
    )
    
    status = models.CharField(
        max_length=20,
        choices=InteractionStatus.choices,
        default=InteractionStatus.PENDING,
        db_index=True
    )
    
    # Message content
    subject = models.CharField(max_length=255, blank=True)
    message_content = models.TextField()
    
    # External tracking
    external_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )  # Heymarket ID, Gmail message ID, Telnyx call ID, etc.
    
    # Timestamps
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # AI Processing
    ai_intent_detected = models.CharField(max_length=100, blank=True, null=True)
    ai_sentiment_score = models.FloatField(null=True, blank=True)  # -1 to 1
    ai_processed_at = models.DateTimeField(null=True, blank=True)
    
    # Response information
    reply_message = models.TextField(blank=True, null=True)
    ai_generated = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'collections_interaction_ledger'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['collection_case', 'created_at']),
            models.Index(fields=['channel', 'status']),
        ]
    
    def __str__(self):
        return f"{self.get_channel_display()} - {self.get_interaction_type_display()} ({self.status})"
