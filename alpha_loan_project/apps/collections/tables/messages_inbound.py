"""MessagesInbound Model - Replies from borrowers"""

from django.db import models


class MessagesInbound(models.Model):
    """
    Stores all inbound messages (replies) received from borrowers.
    Used for tracking responses, intent analysis, and follow-up.
    """
    
    class IntentType(models.TextChoices):
        WILL_PAY = 'will_pay', 'Will Pay'
        REQUEST_DELAY = 'request_delay', 'Request Delay'
        DISPUTE = 'dispute', 'Dispute'
        CANT_PAY = 'cant_pay', 'Cannot Pay'
        QUESTION = 'question', 'Question'
        STOP = 'stop', 'Stop/Opt-out'
        UNCLEAR = 'unclear', 'Unclear'
        NONE = 'none', 'No Intent'
    
    class Channel(models.TextChoices):
        SMS = 'sms', 'SMS'
        EMAIL = 'email', 'Email'
    
    # Links to outbound message
    outbound_message = models.ForeignKey(
        'collections.MessagesOutbound',
        on_delete=models.SET_NULL,
        related_name='replies',
        null=True,
        blank=True,
        help_text="The message this is replying to"
    )
    
    # Links to data tables
    crm_data = models.ForeignKey(
        'collections.CRMData',
        on_delete=models.SET_NULL,
        related_name='inbound_messages',
        null=True,
        blank=True
    )
    ingestion_data = models.ForeignKey(
        'collections.IngestionData',
        on_delete=models.SET_NULL,
        related_name='inbound_messages',
        null=True,
        blank=True
    )
    
    # Row reference
    row_id = models.IntegerField(null=True, blank=True, db_index=True, help_text="CRM Row ID if identifiable")
    
    # Sender info
    from_phone = models.CharField(max_length=50, db_index=True, help_text="Phone message came from")
    from_email = models.EmailField(null=True, blank=True, help_text="Email message came from")
    borrower_name = models.CharField(max_length=255, null=True, blank=True)
    channel = models.CharField(max_length=10, choices=Channel.choices, default=Channel.SMS)
    
    # Message content
    message_content = models.TextField(help_text="Full message text received")
    
    # Webhook/provider data
    provider = models.CharField(max_length=50, null=True, blank=True, help_text="heymarket, twilio, etc.")
    provider_message_id = models.CharField(max_length=100, null=True, blank=True)
    webhook_payload = models.JSONField(null=True, blank=True, help_text="Raw webhook data")
    
    # Intent analysis (by Gemini)
    intent = models.CharField(max_length=20, choices=IntentType.choices, default=IntentType.NONE, db_index=True)
    intent_confidence = models.FloatField(null=True, blank=True, help_text="AI confidence score 0-1")
    intent_analysis = models.JSONField(null=True, blank=True, help_text="Full Gemini intent analysis")
    
    # Extracted commitment (if any)
    commitment_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    commitment_date = models.DateField(null=True, blank=True)
    
    # Processing status
    is_processed = models.BooleanField(default=False, help_text="Has this been processed by AI?")
    requires_human = models.BooleanField(default=False, help_text="Flagged for human review")
    human_notes = models.TextField(null=True, blank=True)
    
    # Timestamps
    received_at = models.DateTimeField(db_index=True, help_text="When message was received")
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'messages_inbound'
        ordering = ['-received_at']
        verbose_name = 'Inbound Message'
        verbose_name_plural = 'Inbound Messages'
        indexes = [
            models.Index(fields=['row_id']),
            models.Index(fields=['from_phone']),
            models.Index(fields=['intent']),
            models.Index(fields=['is_processed']),
            models.Index(fields=['requires_human']),
            models.Index(fields=['received_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Inbound {self.id} - {self.from_phone} - {self.intent}"
    
    def analyze_intent(self, gemini_client):
        """Use Gemini to analyze message intent."""
        from django.utils import timezone
        
        analysis = gemini_client.analyze_response_intent(self.message_content)
        
        self.intent = analysis.get('intent', self.IntentType.UNCLEAR)
        self.intent_confidence = analysis.get('confidence')
        self.intent_analysis = analysis
        
        if 'commitment_amount' in analysis:
            self.commitment_amount = analysis['commitment_amount']
        if 'commitment_date' in analysis:
            self.commitment_date = analysis['commitment_date']
        
        self.is_processed = True
        self.processed_at = timezone.now()
        self.save()
        
        return analysis
