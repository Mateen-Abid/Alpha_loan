"""IngestionData Model - Normalized data for processing"""

from django.db import models


class IngestionData(models.Model):
    """
    Stores normalized/processed data from CRM for collection processing.
    Contains cleaned and standardized fields ready for Gemini message generation.
    """
    
    # Link to raw CRM data
    crm_data = models.ForeignKey(
        'collections.CRMData',
        on_delete=models.CASCADE,
        related_name='ingestion_records',
        null=True,
        blank=True,
        help_text="Link to raw CRM data"
    )
    
    # Primary identifier
    row_id = models.IntegerField(unique=True, db_index=True, help_text="CRM Row ID")
    
    # Borrower info (normalized)
    borrower = models.CharField(max_length=255, help_text="Borrower name (cleaned)")
    
    # Contact info (normalized)
    phone = models.CharField(max_length=50, null=True, blank=True, help_text="Normalized phone (E.164 format)")
    email = models.EmailField(null=True, blank=True, help_text="Validated email")
    
    # Financial data (normalized)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Failed payment amount")
    amount_plus_fee = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Amount + $50 NSF fee")
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Account balance")
    
    # Reason (normalized code)
    reason_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text="Normalized reason code (NSF_EFT, STOP_PMT, ACCOUNT_FROZEN, etc.)"
    )
    
    # Wave (normalized 1-4)
    wave = models.IntegerField(default=1, db_index=True, help_text="Escalation wave (1-4)")
    
    # Processing status
    is_valid = models.BooleanField(default=True, help_text="Is this record valid for processing?")
    validation_errors = models.JSONField(null=True, blank=True, help_text="Any validation errors")
    
    # Message generation tracking
    message_generated = models.BooleanField(default=False, help_text="Has a message been generated?")
    message_sent = models.BooleanField(default=False, help_text="Has the message been sent?")
    last_message_at = models.DateTimeField(null=True, blank=True, help_text="When was last message sent")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ingestion_data'
        ordering = ['-row_id']
        verbose_name = 'Ingestion Data'
        verbose_name_plural = 'Ingestion Data'
        indexes = [
            models.Index(fields=['row_id']),
            models.Index(fields=['borrower']),
            models.Index(fields=['phone']),
            models.Index(fields=['reason_code']),
            models.Index(fields=['wave']),
            models.Index(fields=['is_valid']),
            models.Index(fields=['message_sent']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Ingestion {self.row_id} - {self.borrower}"
    
    @property
    def total_due(self):
        """Alias for amount_plus_fee."""
        return self.amount_plus_fee
    
    def calculate_amount_plus_fee(self, fee=50.00):
        """Calculate and set amount + fee."""
        if self.amount is not None:
            from decimal import Decimal
            self.amount_plus_fee = self.amount + Decimal(str(fee))
        return self.amount_plus_fee
