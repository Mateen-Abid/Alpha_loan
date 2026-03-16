"""Collections Admin Interface"""

from django.contrib import admin
from .models import CollectionCase, TransactionLedger, InteractionLedger, PaymentCommitment


@admin.register(CollectionCase)
class CollectionCaseAdmin(admin.ModelAdmin):
    list_display = ['account_id', 'borrower_name', 'status', 'current_workflow_step', 'get_remaining_balance', 'created_at']
    list_filter = ['status', 'current_workflow_step', 'created_at']
    search_fields = ['account_id', 'borrower_name', 'borrower_phone', 'borrower_email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Account Information', {
            'fields': ('account_id', 'borrower_name', 'borrower_email', 'borrower_phone')
        }),
        ('Collection Details', {
            'fields': ('principal_amount', 'total_due', 'amount_paid')
        }),
        ('Workflow', {
            'fields': ('current_workflow_step', 'workflow_step_started_at')
        }),
        ('Status', {
            'fields': ('status', 'delinquent_date', 'last_contact_at', 'next_followup_at')
        }),
        ('Preferences', {
            'fields': ('does_not_call', 'notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TransactionLedger)
class TransactionLedgerAdmin(admin.ModelAdmin):
    list_display = ['collection_case', 'transaction_type', 'amount', 'posted_date', 'created_at']
    list_filter = ['transaction_type', 'posted_date']
    search_fields = ['collection_case__account_id', 'external_reference']
    readonly_fields = ['created_at']


@admin.register(InteractionLedger)
class InteractionLedgerAdmin(admin.ModelAdmin):
    list_display = ['collection_case', 'channel', 'interaction_type', 'status', 'ai_intent_detected', 'created_at']
    list_filter = ['channel', 'status', 'interaction_type', 'ai_intent_detected']
    search_fields = ['collection_case__account_id', 'external_id']
    readonly_fields = ['created_at', 'sent_at', 'delivered_at', 'read_at', 'replied_at']


@admin.register(PaymentCommitment)
class PaymentCommitmentAdmin(admin.ModelAdmin):
    list_display = ['collection_case', 'committed_amount', 'amount_paid', 'promised_date', 'status']
    list_filter = ['status', 'promised_date']
    search_fields = ['collection_case__account_id']
    readonly_fields = ['created_at', 'updated_at']
