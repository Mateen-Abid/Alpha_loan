"""Collection Service - Core business logic for collections."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from apps.collections.models import (
    CollectionCase,
    InteractionLedger,
    PaymentCommitment,
    TransactionLedger,
)


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
        principal_amount: Decimal,
        total_due: Decimal,
        delinquent_date: date,
        borrower_email: Optional[str] = None,
        partner_row_id: Optional[str] = None,
    ) -> CollectionCase:
        """Create a new collection case"""
        return CollectionCase.objects.create(
            account_id=account_id,
            partner_row_id=partner_row_id,
            borrower_name=borrower_name,
            borrower_phone=borrower_phone,
            borrower_email=borrower_email,
            principal_amount=principal_amount,
            total_due=total_due,
            delinquent_date=delinquent_date,
        )
    
    @staticmethod
    def get_case_by_account_id(account_id: str) -> CollectionCase:
        """Retrieve case by account ID"""
        return CollectionCase.objects.get(account_id=account_id)

    @staticmethod
    def find_case(
        *,
        row_id: Optional[str] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        case_id: Optional[int] = None,
        account_id: Optional[str] = None,
    ) -> Optional[CollectionCase]:
        """Resolve case in priority order by IDs/contact info."""
        if case_id is not None:
            return CollectionCase.objects.filter(id=case_id).first()
        if account_id:
            return CollectionCase.objects.filter(account_id=account_id).first()
        if row_id:
            return CollectionCase.objects.filter(partner_row_id=row_id).first()
        if phone:
            return CollectionCase.objects.filter(borrower_phone=phone).first()
        if email:
            return CollectionCase.objects.filter(borrower_email=email).first()
        return None
    
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
        external_id: Optional[str] = None,
        subject: str = "",
        status: str = InteractionLedger.InteractionStatus.PENDING,
        ai_generated: bool = False,
    ) -> InteractionLedger:
        """Record a communication interaction"""
        return InteractionLedger.objects.create(
            collection_case=case,
            channel=channel,
            interaction_type=interaction_type,
            subject=subject,
            message_content=message_content,
            external_id=external_id,
            status=status,
            ai_generated=ai_generated,
        )
    
    @staticmethod
    def record_transaction(
        case: CollectionCase,
        transaction_type: str,
        amount: Decimal,
        posted_date: date,
        description: str = "",
        created_by: str = "system",
        external_reference: Optional[str] = None,
    ) -> TransactionLedger:
        """Record a financial transaction"""
        return TransactionLedger.objects.create(
            collection_case=case,
            transaction_type=transaction_type,
            amount=amount,
            posted_date=posted_date,
            description=description,
            created_by=created_by,
            external_reference=external_reference,
        )
    
    @staticmethod
    def create_payment_commitment(
        case: CollectionCase,
        committed_amount: Decimal,
        promised_date: date,
        payment_method: str = "",
        commitment_source: str = "",
        notes: str = "",
    ) -> PaymentCommitment:
        """Create a payment commitment"""
        return PaymentCommitment.objects.create(
            collection_case=case,
            committed_amount=committed_amount,
            promised_date=promised_date,
            payment_method=payment_method,
            commitment_source=commitment_source,
            notes=notes,
        )
