"""CollectionCase Repository - Data access for collection cases"""

from .models import CollectionCase


class CollectionCaseRepository:
    """Repository for CollectionCase model operations"""
    
    @staticmethod
    def get_by_account_id(account_id: str):
        """Get case by account ID"""
        return CollectionCase.objects.filter(account_id=account_id).first()
    
    @staticmethod
    def get_by_phone(phone: str):
        """Get cases by phone number"""
        return CollectionCase.objects.filter(borrower_phone=phone)
    
    @staticmethod
    def get_active_cases():
        """Get all active cases"""
        return CollectionCase.objects.filter(status=CollectionCase.CollectionStatus.ACTIVE)
    
    @staticmethod
    def get_cases_by_step(step: str):
        """Get cases at specific workflow step"""
        return CollectionCase.objects.filter(current_workflow_step=step)
    
    @staticmethod
    def get_cases_needing_followup():
        """Get cases that need follow-up"""
        from django.utils import timezone
        return CollectionCase.objects.filter(
            status=CollectionCase.CollectionStatus.ACTIVE,
            next_followup_at__lte=timezone.now()
        )
