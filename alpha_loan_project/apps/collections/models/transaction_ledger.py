"""TransactionLedger Model - Financial event tracking"""

from django.db import models
from .collection_case import CollectionCase


class TransactionLedger(models.Model):
    """
    Tracks all financial transactions and events for a collection case.
    Provides audit trail of payments, fees, and financial adjustments.
    """
    
    class TransactionType(models.TextChoices):
        PAYMENT = 'PAYMENT', 'Payment Received'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        FEE = 'FEE', 'Fee Applied'
        NSF = 'NSF', 'Non-Sufficient Funds'
        REVERSAL = 'REVERSAL', 'Reversal'
    
    collection_case = models.ForeignKey(
        CollectionCase,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    
    transaction_type = models.CharField(
        max_length=20,
        choices=TransactionType.choices,
        db_index=True
    )
    
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    
    # Metadata
    external_reference = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        db_index=True
    )  # Payment gateway transaction ID, check number, etc.
    
    posted_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=255, blank=True)  # System, user, webhook
    
    class Meta:
        db_table = 'collections_transaction_ledger'
        ordering = ['-posted_date', '-created_at']
        indexes = [
            models.Index(fields=['collection_case', 'posted_date']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - ${self.amount} on {self.posted_date}"
