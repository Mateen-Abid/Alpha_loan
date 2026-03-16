"""PaymentCommitment Model - Promise-to-pay tracking"""

from django.db import models
from .collection_case import CollectionCase


class PaymentCommitment(models.Model):
    """
    Tracks borrower promises to pay (commitments).
    Monitors commitment fulfillment and tracks broken commitments.
    """
    
    class CommitmentStatus(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        PARTIAL_PAID = 'PARTIAL_PAID', 'Partially Paid'
        FULFILLED = 'FULFILLED', 'Fulfilled'
        BROKEN = 'BROKEN', 'Broken'
        CANCELLED = 'CANCELLED', 'Cancelled'
    
    collection_case = models.ForeignKey(
        CollectionCase,
        on_delete=models.CASCADE,
        related_name='commitments'
    )
    
    committed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    status = models.CharField(
        max_length=20,
        choices=CommitmentStatus.choices,
        default=CommitmentStatus.PENDING,
        db_index=True
    )
    
    # Dates
    promised_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        help_text="ACH, Check, Credit Card, etc."
    )
    commitment_source = models.CharField(
        max_length=50,
        blank=True,
        help_text="SMS, Voice, Email, etc."
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'collections_payment_commitment'
        ordering = ['-promised_date']
        indexes = [
            models.Index(fields=['collection_case', 'promised_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Commitment ${self.committed_amount} - {self.promised_date}"
    
    def get_remaining_amount(self):
        """Calculate remaining committed amount"""
        return self.committed_amount - self.amount_paid
