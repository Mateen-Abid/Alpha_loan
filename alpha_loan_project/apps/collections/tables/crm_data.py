"""CRMData Model - Stores ALL raw CRM columns from iCollector"""

from django.db import models


class CRMData(models.Model):
    """
    Stores raw CRM data fetched from iCollector API.
    Contains ALL columns exactly as received from the CRM.
    """
    
    # Primary identifiers
    row_id = models.IntegerField(unique=True, db_index=True, help_text="CRM Row ID (e.g., 251044)")
    board_id = models.IntegerField(default=70, db_index=True, help_text="CRM Board ID")
    group_id = models.IntegerField(null=True, blank=True, help_text="CRM Group ID")
    group_name = models.CharField(max_length=255, null=True, blank=True)
    
    # Core borrower info
    client = models.CharField(max_length=255, null=True, blank=True, help_text="Client/Borrower name")
    
    # Contact info
    phone_number_raw = models.CharField(max_length=50, null=True, blank=True, help_text="Raw phone number")
    phone_number_formatted = models.CharField(max_length=50, null=True, blank=True)
    phone_number_country = models.CharField(max_length=10, null=True, blank=True)
    phone_number_valid = models.BooleanField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    
    # Financial data
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Failed payment amount")
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Account balance")
    
    # Collection status
    reason = models.CharField(max_length=255, null=True, blank=True, help_text="Raw reason from CRM")
    action = models.CharField(max_length=100, null=True, blank=True, help_text="Action field (opt_0, 3rd NSF, etc.)")
    wave = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Escalation wave (1-4)")
    
    # Agent and assignment
    agent = models.CharField(max_length=255, null=True, blank=True, help_text="Assigned agent")
    
    # Additional fields
    lang = models.CharField(max_length=50, null=True, blank=True, help_text="Language preference")
    date = models.DateField(null=True, blank=True, help_text="Date field from CRM")
    cell = models.CharField(max_length=100, null=True, blank=True)
    ref = models.TextField(null=True, blank=True, help_text="Reference field (JSON)")
    time_zone = models.CharField(max_length=100, null=True, blank=True)
    work = models.CharField(max_length=100, null=True, blank=True)
    comment = models.TextField(null=True, blank=True, help_text="CRM comments")
    
    # Email metrics
    email_metric_sent_count = models.IntegerField(null=True, blank=True, default=0)
    email_metric_opened_count = models.IntegerField(null=True, blank=True, default=0)
    email_metric_last_sent = models.DateTimeField(null=True, blank=True)
    email_metric_last_opened = models.DateTimeField(null=True, blank=True)
    
    # CRM timestamps
    last_updated_start = models.DateTimeField(null=True, blank=True, help_text="CRM Last Updated start")
    last_updated_end = models.DateTimeField(null=True, blank=True, help_text="CRM Last Updated end")
    
    # World clock (stored as JSON string if complex)
    world_clock = models.TextField(null=True, blank=True)
    
    # Raw data backup (store entire columns dict as JSON for any missed fields)
    raw_columns_json = models.JSONField(null=True, blank=True, help_text="Complete raw columns data")
    
    # Sync tracking
    synced_at = models.DateTimeField(auto_now=True, help_text="Last sync from CRM")
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'crm_data'
        ordering = ['-row_id']
        verbose_name = 'CRM Data'
        verbose_name_plural = 'CRM Data'
        indexes = [
            models.Index(fields=['row_id']),
            models.Index(fields=['board_id', 'group_id']),
            models.Index(fields=['client']),
            models.Index(fields=['phone_number_raw']),
            models.Index(fields=['wave']),
            models.Index(fields=['reason']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"CRM Row {self.row_id} - {self.client or 'Unknown'}"
    
    @property
    def phone(self):
        """Return the best available phone number."""
        return self.phone_number_raw or self.phone_number_formatted
    
    @property
    def wave_int(self):
        """Return wave as integer (1-4), normalized."""
        if self.wave is None:
            return 1
        wave_val = int(self.wave)
        return max(1, min(4, wave_val))
