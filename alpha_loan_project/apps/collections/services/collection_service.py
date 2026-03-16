"""Collection Service - Core business logic for collections"""

from .models import CollectionCase, TransactionLedger, InteractionLedger, PaymentCommitment


class CollectionService:
    """
    Service layer for collection case management.
    Handles business logic for collection operations.
    """
    
    @staticmethod
    def create_collection_case(
        account_id: str,
        borrower_name: str,
        borrower_phone: str,
        principal_amount: float,
        total_due: float,
        delinquent_date
    ) -> CollectionCase:
        """Create a new collection case"""
        return CollectionCase.objects.create(
            account_id=account_id,
            borrower_name=borrower_name,
            borrower_phone=borrower_phone,
            principal_amount=principal_amount,
            total_due=total_due,
            delinquent_date=delinquent_date,
        )
    
    @staticmethod
    def get_case_by_account_id(account_id: str) -> CollectionCase:
        """Retrieve case by account ID"""
        return CollectionCase.objects.get(account_id=account_id)
    
    @staticmethod
    def update_case_workflow_step(case: CollectionCase, new_step: str) -> CollectionCase:
        """Update workflow step for a case"""
        case.current_workflow_step = new_step
        case.save()
        return case
    
    @staticmethod
    def record_interaction(
        case: CollectionCase,
        channel: str,
        interaction_type: str,
        message_content: str,
        external_id: str = None
    ) -> InteractionLedger:
        """Record a communication interaction"""
        return InteractionLedger.objects.create(
            collection_case=case,
            channel=channel,
            interaction_type=interaction_type,
            message_content=message_content,
            external_id=external_id,
        )
    
    @staticmethod
    def record_transaction(
        case: CollectionCase,
        transaction_type: str,
        amount: float,
        posted_date,
        description: str = ""
    ) -> TransactionLedger:
        """Record a financial transaction"""
        return TransactionLedger.objects.create(
            collection_case=case,
            transaction_type=transaction_type,
            amount=amount,
            posted_date=posted_date,
            description=description,
        )
    
    @staticmethod
    def create_payment_commitment(
        case: CollectionCase,
        committed_amount: float,
        promised_date,
        payment_method: str = ""
    ) -> PaymentCommitment:
        """Create a payment commitment"""
        return PaymentCommitment.objects.create(
            collection_case=case,
            committed_amount=committed_amount,
            promised_date=promised_date,
            payment_method=payment_method,
        )
