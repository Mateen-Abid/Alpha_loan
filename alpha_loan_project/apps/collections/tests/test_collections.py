"""Collections App Tests"""

import pytest
from django.test import TestCase
from apps.collections.models import CollectionCase
from apps.collections.services.collection_service import CollectionService
from django.utils import timezone
from datetime import date


class CollectionCaseTests(TestCase):
    """Tests for CollectionCase model"""
    
    def setUp(self):
        """Set up test data"""
        self.case = CollectionService.create_collection_case(
            account_id='ACC001',
            borrower_name='John Doe',
            borrower_phone='+14155552671',
            principal_amount=1000.00,
            total_due=1200.00,
            delinquent_date=date.today()
        )
    
    def test_create_collection_case(self):
        """Test creating a collection case"""
        self.assertEqual(self.case.account_id, 'ACC001')
        self.assertEqual(self.case.borrower_name, 'John Doe')
        self.assertEqual(self.case.status, 'ACTIVE')
    
    def test_get_remaining_balance(self):
        """Test calculating remaining balance"""
        remaining = self.case.get_remaining_balance()
        self.assertEqual(remaining, 1200.00)
    
    def test_workflow_state_default(self):
        """Test default workflow state"""
        self.assertEqual(self.case.current_workflow_step, 'STEP_1')
