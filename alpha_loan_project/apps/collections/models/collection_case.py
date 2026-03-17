"""CollectionCase Model - Represents a delinquent account"""

from django.db import models
from django.utils import timezone


class CollectionCase(models.Model):
    """
    Represents a delinquent loan account in the collection workflow.
    Tracks the account status, current workflow step, and key dates.
    """
    
    class WorkflowStep(models.TextChoices):
        STEP_1 = 'STEP_1', 'Immediate Payment'
        STEP_2 = 'STEP_2', 'Double Payment'
        STEP_3 = 'STEP_3', 'Add NSF to Next Payment'
        STEP_4 = 'STEP_4', 'Split NSF'
        FINAL_PRESSURE = 'FINAL_PRESSURE', 'Final Pressure'
    
    class CollectionStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        RESOLVED = 'RESOLVED', 'Resolved'
        LOST = 'LOST', 'Lost'
        SUSPENDED = 'SUSPENDED', 'Suspended'

    class AutomationStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        PAUSED = 'PAUSED', 'Paused'
        STOPPED = 'STOPPED', 'Stopped'
    
    # Account identifiers
    account_id = models.CharField(max_length=100, unique=True, db_index=True)
    partner_row_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True)
    borrower_name = models.CharField(max_length=255)
    borrower_email = models.EmailField(null=True, blank=True)
    borrower_phone = models.CharField(max_length=20, db_index=True)
    
    # Collection info
    principal_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_due = models.DecimalField(max_digits=12, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Workflow state
    current_workflow_step = models.CharField(
        max_length=20,
        choices=WorkflowStep.choices,
        default=WorkflowStep.STEP_1,
        db_index=True
    )
    workflow_step_started_at = models.DateTimeField(auto_now_add=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=CollectionStatus.choices,
        default=CollectionStatus.ACTIVE,
        db_index=True
    )
    automation_status = models.CharField(
        max_length=20,
        choices=AutomationStatus.choices,
        default=AutomationStatus.ACTIVE,
        db_index=True,
    )
    
    # Key dates
    delinquent_date = models.DateField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_contact_at = models.DateTimeField(null=True, blank=True, db_index=True)
    next_followup_at = models.DateTimeField(null=True, blank=True, db_index=True)
    next_action_time = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Tracking
    does_not_call = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'collections_case'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'current_workflow_step']),
            models.Index(fields=['automation_status', 'next_action_time']),
            models.Index(fields=['borrower_phone']),
            models.Index(fields=['next_followup_at']),
        ]
    
    def __str__(self):
        return f"Case {self.account_id} - {self.borrower_name}"
    
    def get_age_in_days(self):
        """Return days since account became delinquent"""
        return (timezone.now().date() - self.delinquent_date).days
    
    def get_remaining_balance(self):
        """Calculate remaining balance"""
        return self.total_due - self.amount_paid
