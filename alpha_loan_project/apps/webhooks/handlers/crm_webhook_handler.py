"""CRM Webhook Handler - Payment and case event webhooks"""

import json
from typing import Dict
from apps.collections.services.collection_service import CollectionService


class CRMWebhookHandler:
    """Handles webhooks from CRM system"""
    
    @staticmethod
    def handle_payment_webhook(payload: Dict) -> Dict:
        """
        Handle payment received webhook from CRM.
        
        Args:
            payload: Webhook payload with payment details
        
        Returns:
            Processing result
        """
        try:
            account_id = payload.get('account_id')
            amount = payload.get('amount')
            transaction_date = payload.get('date')
            
            # Retrieve case and record payment
            case = CollectionService.get_case_by_account_id(account_id)
            if case:
                transaction = CollectionService.record_transaction(
                    case=case,
                    transaction_type='PAYMENT',
                    amount=amount,
                    posted_date=transaction_date,
                    description='Payment received via CRM webhook'
                )
                
                # Update case if account is resolved
                remaining = case.get_remaining_balance()
                if remaining <= 0:
                    case.status = 'RESOLVED'
                    case.save()
                
                return {
                    'status': 'success',
                    'transaction_id': transaction.id
                }
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
    
    @staticmethod
    def handle_account_update_webhook(payload: Dict) -> Dict:
        """Handle account update webhook"""
        try:
            account_id = payload.get('account_id')
            updates = payload.get('updates', {})
            
            case = CollectionService.get_case_by_account_id(account_id)
            if case:
                for field, value in updates.items():
                    if hasattr(case, field):
                        setattr(case, field, value)
                case.save()
                
                return {'status': 'success', 'case_id': case.id}
        except Exception as e:
            return {'status': 'failed', 'error': str(e)}
