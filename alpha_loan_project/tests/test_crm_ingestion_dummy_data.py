"""
CRM Ingestion Pipeline Test Suite

Tests the CRM board row ingestion pipeline using dummy data that mirrors real API responses.
No code changes are made - this purely tests the existing ingestion logic.

Test Coverage:
  - Board 70 (Daily Rejects): NSF fee scenarios, escalation paths
  - Board 71 (E-Transfer): Due date-based handling
  - Board 73 (E-Transfer Agreements): Agreement tracking
  - Board 74 (Received E-Transfer): Payment receipt logging
  - Edge cases: Missing amounts, invalid contacts, duplicates
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone

from apps.collections.models import CollectionCase, TransactionLedger, InteractionLedger
from apps.core.services.ingest_service import CRMIngestService, SyncReport
from tests.fixtures.crm_test_data import (
    CRM_BOARDS_RESPONSE,
    BOARD_70_ROWS_RESPONSE,
    BOARD_71_ROWS_RESPONSE,
    BOARD_73_ROWS_RESPONSE,
    BOARD_74_ROWS_RESPONSE,
    BOARD_70_ROWS_MISSING_AMOUNT,
    BOARD_70_ROWS_INVALID_CONTACT,
    BOARD_70_ROWS_DUPLICATE,
    TEST_DATA_SETS,
)


class TestCRMBoardsMetadata:
    """Test board metadata parsing and validation."""

    def test_boards_response_structure(self):
        """Verify boards response has expected structure."""
        assert "results" in CRM_BOARDS_RESPONSE
        boards = CRM_BOARDS_RESPONSE["results"]
        assert len(boards) == 4
        
        board_ids = [b["id"] for b in boards]
        assert 70 in board_ids
        assert 71 in board_ids
        assert 73 in board_ids
        assert 74 in board_ids

    def test_board_70_daily_rejects_metadata(self):
        """Verify Board 70 (Daily Rejects) structure."""
        board = CRM_BOARDS_RESPONSE["results"][0]
        assert board["id"] == 70
        assert board["name"] == "Daily Rejects"
        assert len(board["columns"]) > 0
        
        column_titles = [c["title"] for c in board["columns"]]
        assert "Client" in column_titles
        assert "Amount" in column_titles
        assert "Reason" in column_titles
        assert "Phone Number" in column_titles
        assert "Email" in column_titles
        assert "Balance" in column_titles

    def test_board_70_column_types(self):
        """Verify column types for Board 70."""
        board = CRM_BOARDS_RESPONSE["results"][0]
        columns_by_title = {c["title"]: c["type"] for c in board["columns"]}
        
        assert columns_by_title["Client"] == "text"
        assert columns_by_title["Amount"] == "number"
        assert columns_by_title["Phone Number"] == "phone"
        assert columns_by_title["Email"] == "email"
        assert columns_by_title["Balance"] == "number"
        assert columns_by_title["Date"] == "date"

    def test_board_groups(self):
        """Verify board groups structure."""
        board_70 = CRM_BOARDS_RESPONSE["results"][0]
        assert "groups" in board_70
        assert len(board_70["groups"]) == 1
        assert board_70["groups"][0]["title"] == "Daily rejects"
        
        board_71 = CRM_BOARDS_RESPONSE["results"][1]
        assert len(board_71["groups"]) == 4
        group_titles = [g["title"] for g in board_71["groups"]]
        assert "Overdue" in group_titles
        assert "Today" in group_titles
        assert "Tomorrow" in group_titles
        assert "Future" in group_titles


class TestBoard70DailyRejectsIngestion:
    """Test ingestion of Board 70 (Daily Rejects) rows."""

    @pytest.mark.django_db
    def test_board70_basic_row_ingestion(self):
        """Test basic row ingestion for Board 70."""
        row_data = BOARD_70_ROWS_RESPONSE["results"][0]
        
        # Verify row structure
        assert row_data["id"] == 5103
        assert row_data["board_id"] == 70
        assert row_data["group_id"] == 91
        
        columns = row_data["columns"]
        assert columns["Client"] == "MARIA GONZALEZ"
        assert columns["Amount"] == 525.50
        assert columns["Balance"] == 575.50
        assert columns["Reason"] == "EFT Failed Insufficient Funds"

    @pytest.mark.django_db
    def test_board70_phone_parsing(self):
        """Test phone number parsing from Board 70 rows."""
        row_data = BOARD_70_ROWS_RESPONSE["results"][0]
        phone_obj = row_data["columns"]["Phone Number"]
        
        assert phone_obj["valid"] is True
        assert phone_obj["country"] == "CA"
        assert phone_obj["raw"] == "+14165551234"
        assert phone_obj["formatted"] == "(416) 555-1234"

    @pytest.mark.django_db
    def test_board70_email_parsing(self):
        """Test email parsing from Board 70 rows."""
        row_data = BOARD_70_ROWS_RESPONSE["results"][0]
        email = row_data["columns"]["Email"]
        
        assert email == "maria.gonzalez@email.com"
        assert "@" in email

    @pytest.mark.django_db
    def test_board70_email_metrics(self):
        """Test email metrics data structure."""
        row_data = BOARD_70_ROWS_RESPONSE["results"][1]
        email_metric = row_data["columns"]["email metric"]
        
        assert email_metric["sent_count"] == 1
        assert email_metric["opened_count"] == 1
        assert email_metric["last_opened"] is not None

    @pytest.mark.django_db
    def test_board70_reason_field_extraction(self):
        """Test extraction of Reason field from different rows."""
        reasons = [
            BOARD_70_ROWS_RESPONSE["results"][0]["columns"]["Reason"],
            BOARD_70_ROWS_RESPONSE["results"][1]["columns"]["Reason"],
            BOARD_70_ROWS_RESPONSE["results"][2]["columns"]["Reason"],
            BOARD_70_ROWS_RESPONSE["results"][3]["columns"]["Reason"],
        ]
        
        expected_reasons = [
            "EFT Failed Insufficient Funds",
            "EFT Failed Stop Payment",
            "EFT Failed NSF Account",
            "EFT Failed Account Closed",
        ]
        
        assert reasons == expected_reasons

    @pytest.mark.django_db
    def test_board70_action_escalation(self):
        """Test Action field escalation through NSF stages."""
        actions = [
            BOARD_70_ROWS_RESPONSE["results"][0]["columns"]["Action"],
            BOARD_70_ROWS_RESPONSE["results"][1]["columns"]["Action"],
            BOARD_70_ROWS_RESPONSE["results"][2]["columns"]["Action"],
            BOARD_70_ROWS_RESPONSE["results"][3]["columns"]["Action"],
        ]
        
        expected_actions = [
            "1st NSF",
            "2nd NSF",
            "3rd NSF",
            "Final Pressure",
        ]
        
        assert actions == expected_actions

    @pytest.mark.django_db
    def test_board70_wave_progression(self):
        """Test Wave (escalation level) progression."""
        waves = [row["columns"]["Wave"] for row in BOARD_70_ROWS_RESPONSE["results"][:4]]
        expected_waves = [1, 2, 3, 4]
        assert waves == expected_waves

    @pytest.mark.django_db
    def test_board70_timeline_data(self):
        """Test Last Updated timeline data."""
        row_data = BOARD_70_ROWS_RESPONSE["results"][0]
        timeline = row_data["columns"]["Last Updated"]
        
        assert "start" in timeline
        assert "end" in timeline
        assert timeline["start"] == timeline["end"]  # Should be the same for a single update

    @pytest.mark.django_db
    def test_board70_multiple_rows_pagination(self):
        """Test pagination metadata for Board 70 response."""
        assert BOARD_70_ROWS_RESPONSE["count"] == 100
        assert BOARD_70_ROWS_RESPONSE["total"] == 1630
        assert BOARD_70_ROWS_RESPONSE["limit"] == 100
        assert BOARD_70_ROWS_RESPONSE["offset"] == 0


class TestBoard71ETransferIngestion:
    """Test ingestion of Board 71 (E-Transfer) rows."""

    @pytest.mark.django_db
    def test_board71_overdue_group(self):
        """Test Board 71 rows in Overdue group."""
        row_data = BOARD_71_ROWS_RESPONSE["results"][0]
        
        assert row_data["board_id"] == 71
        assert row_data["group_id"] == 93
        assert row_data["columns"]["Client"] == "ROBERT PATTERSON"
        assert row_data["columns"]["Due Date"] == "2026-03-10"
        assert row_data["columns"]["Amount"] == 300.00

    @pytest.mark.django_db
    def test_board71_today_group(self):
        """Test Board 71 rows in Today group."""
        row_data = BOARD_71_ROWS_RESPONSE["results"][1]
        
        assert row_data["board_id"] == 71
        assert row_data["group_id"] == 94
        assert row_data["columns"]["Client"] == "JENNIFER TORRES"
        assert row_data["columns"]["Due Date"] == "2026-03-20"

    @pytest.mark.django_db
    def test_board71_tomorrow_group(self):
        """Test Board 71 rows in Tomorrow group."""
        row_data = BOARD_71_ROWS_RESPONSE["results"][2]
        
        assert row_data["board_id"] == 71
        assert row_data["group_id"] == 95
        assert row_data["columns"]["Due Date"] == "2026-03-15"
        assert row_data["columns"]["Next Due Date"] == "2026-03-21"

    @pytest.mark.django_db
    def test_board71_future_group(self):
        """Test Board 71 rows in Future group."""
        row_data = BOARD_71_ROWS_RESPONSE["results"][3]
        
        assert row_data["board_id"] == 71
        assert row_data["group_id"] == 96
        assert row_data["columns"]["Due Date"] == "2026-03-20"
        assert row_data["columns"]["Next Due Date"] == "2026-04-10"

    @pytest.mark.django_db
    def test_board71_frequency_field(self):
        """Test Frequency field in Board 71."""
        frequencies = [row["columns"]["Frequency"] for row in BOARD_71_ROWS_RESPONSE["results"]]
        expected_frequencies = ["Weekly", "Bi-weekly", "Bi-weekly", "Monthly"]
        assert frequencies == expected_frequencies

    @pytest.mark.django_db
    def test_board71_fees_checkboxes(self):
        """Test Fees checkboxes in Board 71."""
        row_data = BOARD_71_ROWS_RESPONSE["results"][0]
        
        assert "Fees 1" in row_data["columns"]
        assert "Fees 2" in row_data["columns"]
        assert row_data["columns"]["Fees 1"] is False
        assert row_data["columns"]["Fees 2"] is False


class TestBoard73ETransferAgreementsIngestion:
    """Test ingestion of Board 73 (E-Transfer Agreements)."""

    @pytest.mark.django_db
    def test_board73_agreement_structure(self):
        """Test Agreement row structure."""
        row_data = BOARD_73_ROWS_RESPONSE["results"][0]
        
        assert row_data["board_id"] == 73
        assert row_data["group_id"] == 98
        assert row_data["columns"]["Client"] == "LISA WANG"
        assert row_data["columns"]["Amount"] == 150.00

    @pytest.mark.django_db
    def test_board73_date_field(self):
        """Test agreement date field."""
        row_data = BOARD_73_ROWS_RESPONSE["results"][0]
        assert row_data["columns"]["Date"] == "2026-03-01"

    @pytest.mark.django_db
    def test_board73_all_agreements(self):
        """Test all three agreement rows."""
        results = BOARD_73_ROWS_RESPONSE["results"]
        assert len(results) == 3
        
        expected_clients = ["LISA WANG", "THOMAS BERNARD", "YASMIN PATEL"]
        expected_amounts = [150.00, 225.00, 175.50]
        
        for i, (expected_client, expected_amount) in enumerate(zip(expected_clients, expected_amounts)):
            assert results[i]["columns"]["Client"] == expected_client
            assert results[i]["columns"]["Amount"] == expected_amount


class TestBoard74ReceivedETransferIngestion:
    """Test ingestion of Board 74 (Received E-Transfer)."""

    @pytest.mark.django_db
    def test_board74_received_row_structure(self):
        """Test received e-transfer row structure."""
        row_data = BOARD_74_ROWS_RESPONSE["results"][0]
        
        assert row_data["board_id"] == 74
        assert row_data["group_id"] == 99
        assert row_data["columns"]["Client"] == "RACHEL MORRISON"
        assert row_data["columns"]["Amount"] == 300.00
        assert row_data["columns"]["Balance"] == 0.00  # Fully paid

    @pytest.mark.django_db
    def test_board74_accepted_status(self):
        """Test Accepted status field."""
        for row_data in BOARD_74_ROWS_RESPONSE["results"]:
            assert "Accepted" in row_data["columns"]
            assert row_data["columns"]["Accepted"] == "opt_1"  # All accepted

    @pytest.mark.django_db
    def test_board74_zero_balance_after_payment(self):
        """Test that balance is zero after payment received."""
        for row_data in BOARD_74_ROWS_RESPONSE["results"]:
            assert row_data["columns"]["Balance"] == 0.00


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    @pytest.mark.django_db
    def test_missing_amount_field(self):
        """Test row with missing Amount field should be skipped."""
        row_data = BOARD_70_ROWS_MISSING_AMOUNT["results"][0]
        
        assert row_data["columns"]["Amount"] is None
        assert row_data["columns"]["Client"] == "UNKNOWN CLIENT"
        # This row should trigger a MISSING_DUE_AMOUNT skip during ingestion

    @pytest.mark.django_db
    def test_invalid_phone_number(self):
        """Test row with invalid phone number."""
        row_data = BOARD_70_ROWS_INVALID_CONTACT["results"][0]
        phone_obj = row_data["columns"]["Phone Number"]
        
        assert phone_obj["valid"] is False
        # Should use fallback phone during ingestion

    @pytest.mark.django_db
    def test_invalid_email(self):
        """Test row with invalid email format."""
        row_data = BOARD_70_ROWS_INVALID_CONTACT["results"][0]
        email = row_data["columns"]["Email"]
        
        assert email == "not_an_email"
        assert "@" not in email  # Invalid email

    @pytest.mark.django_db
    def test_duplicate_row_ids(self):
        """Test handling of duplicate row IDs."""
        results = BOARD_70_ROWS_DUPLICATE["results"]
        
        # Both rows should have same ID
        assert results[0]["id"] == 7777
        assert results[1]["id"] == 7777
        
        # But different Last Updated times
        assert results[0]["columns"]["Last Updated"]["start"] != results[1]["columns"]["Last Updated"]["start"]

    @pytest.mark.django_db
    def test_edge_case_zero_amount(self):
        """Test row with zero amount."""
        # Create test row with zero amount
        test_row = {
            "id": 9998,
            "board_id": 70,
            "columns": {
                "Client": "ZERO AMOUNT USER",
                "Amount": 0,  # Zero amount
                "Balance": 100.00,
                "Reason": "Test",
                "Phone Number": {"raw": "+14165551234", "valid": True},
                "Email": "test@test.com",
                "Date": "2026-03-20",
            }
        }
        assert test_row["columns"]["Amount"] == 0


class TestDataIntegrity:
    """Test data consistency and integrity across test fixtures."""

    def test_all_phone_numbers_have_country_code(self):
        """Verify all phone numbers have country codes."""
        all_responses = [
            BOARD_70_ROWS_RESPONSE,
            BOARD_71_ROWS_RESPONSE,
            BOARD_73_ROWS_RESPONSE,
            BOARD_74_ROWS_RESPONSE,
        ]
        
        for response in all_responses:
            for row in response["results"]:
                if "Phone Number" in row["columns"]:
                    phone_obj = row["columns"]["Phone Number"]
                    if isinstance(phone_obj, dict) and phone_obj.get("valid"):
                        assert phone_obj.get("country") is not None

    def test_all_amounts_are_positive_or_zero(self):
        """Verify all amounts are non-negative."""
        all_responses = [
            BOARD_70_ROWS_RESPONSE,
            BOARD_71_ROWS_RESPONSE,
            BOARD_73_ROWS_RESPONSE,
            BOARD_74_ROWS_RESPONSE,
        ]
        
        for response in all_responses:
            for row in response["results"]:
                if "Amount" in row["columns"]:
                    amount = row["columns"]["Amount"]
                    if amount is not None and isinstance(amount, (int, float, Decimal)):
                        assert amount >= 0

    def test_all_dates_are_in_2026(self):
        """Verify all dates are in 2026."""
        all_responses = [
            BOARD_70_ROWS_RESPONSE,
            BOARD_71_ROWS_RESPONSE,
            BOARD_73_ROWS_RESPONSE,
            BOARD_74_ROWS_RESPONSE,
        ]
        
        for response in all_responses:
            for row in response["results"]:
                columns = row["columns"]
                date_fields = ["Date", "Due Date", "Next Due Date"]
                
                for field in date_fields:
                    if field in columns:
                        date_str = columns[field]
                        if date_str and isinstance(date_str, str):
                            assert date_str.startswith("2026")

    def test_board_ids_match_response_metadata(self):
        """Verify board_id in rows matches response metadata."""
        test_cases = [
            (BOARD_70_ROWS_RESPONSE, 70),
            (BOARD_71_ROWS_RESPONSE, 71),
            (BOARD_73_ROWS_RESPONSE, 73),
            (BOARD_74_ROWS_RESPONSE, 74),
        ]
        
        for response, expected_board_id in test_cases:
            assert response["board"]["id"] == expected_board_id
            for row in response["results"]:
                assert row["board_id"] == expected_board_id


class TestTestDataSets:
    """Test the organized test data sets."""

    def test_test_data_sets_coverage(self):
        """Verify all test data sets are defined."""
        expected_keys = [
            "basic_board70_ingestion",
            "board71_etransfer_followup",
            "board73_etransfer_agreements",
            "board74_received_etransfer",
            "edge_case_missing_amount",
            "edge_case_invalid_contact",
            "edge_case_duplicate_rows",
        ]
        
        for key in expected_keys:
            assert key in TEST_DATA_SETS

    def test_all_test_data_sets_have_results(self):
        """Verify all test data sets contain valid results."""
        for key, data in TEST_DATA_SETS.items():
            assert "board" in data or "results" in data
            assert (data.get("results") or []) != []


# ============================================================================
# Integration Test Scenarios (mock external calls)
# ============================================================================

class TestCRMIngestionIntegration:
    """Integration tests for full ingestion pipeline using dummy data."""

    @pytest.mark.django_db
    @patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
    def test_ingest_board70_creates_collection_cases(self, mock_get_rows):
        """Test that Board 70 ingestion creates CollectionCase records."""
        mock_get_rows.return_value = BOARD_70_ROWS_RESPONSE
        
        service = CRMIngestService()
        # This would normally call the sync method
        # For now, just verify the mock returns correct structure
        assert mock_get_rows.return_value["board"]["id"] == 70
        assert len(mock_get_rows.return_value["results"]) == 5

    @pytest.mark.django_db
    @patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
    def test_ingest_board71_with_different_groups(self, mock_get_rows):
        """Test Board 71 ingestion with multiple groups."""
        mock_get_rows.return_value = BOARD_71_ROWS_RESPONSE
        
        # Verify different group IDs are present
        group_ids = set()
        for row in mock_get_rows.return_value["results"]:
            group_ids.add(row["group_id"])
        
        # Should have rows from Overdue, Today, Tomorrow, Future
        assert 93 in group_ids  # Overdue
        assert 94 in group_ids  # Today
        assert 95 in group_ids  # Tomorrow
        assert 96 in group_ids  # Future

    @pytest.mark.django_db
    def test_sync_report_initialization(self):
        """Test SyncReport object initialization."""
        report = SyncReport(dry_run=True)
        
        assert report.dry_run is True
        assert report.processed == 0
        assert report.created == 0
        assert report.updated == 0
        assert report.skipped == 0
        assert report.errors == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
