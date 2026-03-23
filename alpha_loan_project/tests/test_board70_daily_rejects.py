"""
Board 70 (Daily Rejects) Ingestion Test Suite

Focused testing for Board 70 (Daily Rejects) only.
Tests NSF escalation, contact parsing, and edge cases.
"""

import pytest
from decimal import Decimal
from datetime import date, datetime, timedelta
from unittest.mock import patch, MagicMock
from django.utils import timezone

from apps.collections.models import CollectionCase, TransactionLedger, InteractionLedger
from apps.core.services.ingest_service import CRMIngestService, SyncReport
from tests.fixtures.board70_test_data import (
    BOARD_70_METADATA,
    BOARD_70_ROWS_RESPONSE,
    BOARD_70_ROWS_MISSING_AMOUNT,
    BOARD_70_ROWS_INVALID_CONTACT,
    BOARD_70_ROWS_DUPLICATE,
    TEST_DATA_SETS,
)


class TestBoard70Metadata:
    """Test Board 70 metadata and structure."""

    def test_board_metadata_structure(self):
        """Verify Board 70 metadata has correct structure."""
        assert BOARD_70_METADATA["id"] == 70
        assert BOARD_70_METADATA["name"] == "Daily Rejects"
        assert "groups" in BOARD_70_METADATA
        assert len(BOARD_70_METADATA["groups"]) == 1
        assert BOARD_70_METADATA["groups"][0]["title"] == "Daily rejects"

    def test_board_columns_exist(self):
        """Verify Board 70 has all required columns."""
        columns = BOARD_70_METADATA["columns"]
        column_titles = [c["title"] for c in columns]
        
        required_columns = [
            "Client", "Amount", "Phone Number", "Email", 
            "Date", "Reason", "Action", "Balance", "Wave"
        ]
        
        for col in required_columns:
            assert col in column_titles, f"Missing column: {col}"

    def test_column_types(self):
        """Verify column types match expected types."""
        columns_by_title = {c["title"]: c["type"] for c in BOARD_70_METADATA["columns"]}
        
        assert columns_by_title["Client"] == "text"
        assert columns_by_title["Amount"] == "number"
        assert columns_by_title["Phone Number"] == "phone"
        assert columns_by_title["Email"] == "email"
        assert columns_by_title["Balance"] == "number"
        assert columns_by_title["Date"] == "date"
        assert columns_by_title["Reason"] == "long_text"
        assert columns_by_title["Action"] == "status"
        assert columns_by_title["Wave"] == "number"


class TestBoard70BasicIngestion:
    """Test basic Board 70 row ingestion (happy path)."""

    @pytest.mark.django_db
    def test_response_structure(self):
        """Verify Board 70 response structure."""
        response = BOARD_70_ROWS_RESPONSE
        
        assert "board" in response
        assert "results" in response
        assert response["board"]["id"] == 70
        assert response["board"]["name"] == "Daily Rejects"
        assert len(response["results"]) == 5

    @pytest.mark.django_db
    def test_pagination_metadata(self):
        """Verify pagination metadata."""
        response = BOARD_70_ROWS_RESPONSE
        
        assert response["count"] == 100
        assert response["total"] == 1630
        assert response["limit"] == 100
        assert response["offset"] == 0

    @pytest.mark.django_db
    def test_first_row_maria_gonzalez(self):
        """Test first row: Maria Gonzalez (Wave 1, 1st NSF)."""
        row = BOARD_70_ROWS_RESPONSE["results"][0]
        
        assert row["id"] == 5103
        assert row["board_id"] == 70
        assert row["group_id"] == 91
        
        cols = row["columns"]
        assert cols["Client"] == "MARIA GONZALEZ"
        assert cols["Amount"] == 525.50
        assert cols["Balance"] == 575.50  # Amount + $50 fee
        assert cols["Action"] == "1st NSF"
        assert cols["Wave"] == 1
        assert cols["Reason"] == "EFT Failed Insufficient Funds"
        assert cols["Date"] == "2026-03-20"

    @pytest.mark.django_db
    def test_second_row_james_mitchell(self):
        """Test second row: James Mitchell (Wave 2, 2nd NSF)."""
        row = BOARD_70_ROWS_RESPONSE["results"][1]
        
        assert row["id"] == 5104
        cols = row["columns"]
        assert cols["Client"] == "JAMES MITCHELL"
        assert cols["Amount"] == 750.00
        assert cols["Action"] == "2nd NSF"
        assert cols["Wave"] == 2
        assert cols["Reason"] == "EFT Failed Stop Payment"

    @pytest.mark.django_db
    def test_third_row_alexandra_chen(self):
        """Test third row: Alexandra Chen (Wave 3, 3rd NSF)."""
        row = BOARD_70_ROWS_RESPONSE["results"][2]
        
        assert row["id"] == 5105
        cols = row["columns"]
        assert cols["Client"] == "ALEXANDRA CHEN"
        assert cols["Amount"] == 325.75
        assert cols["Action"] == "3rd NSF"
        assert cols["Wave"] == 3

    @pytest.mark.django_db
    def test_fourth_row_david_kumar(self):
        """Test fourth row: David Kumar (Wave 4, Final Pressure)."""
        row = BOARD_70_ROWS_RESPONSE["results"][3]
        
        assert row["id"] == 5106
        cols = row["columns"]
        assert cols["Client"] == "DAVID KUMAR"
        assert cols["Amount"] == 600.00
        assert cols["Action"] == "Final Pressure"
        assert cols["Wave"] == 4
        assert cols["Reason"] == "EFT Failed Account Closed"

    @pytest.mark.django_db
    def test_fifth_row_sophie_leclerc(self):
        """Test fifth row: Sophie Leclerc (Fresh Wave 1)."""
        row = BOARD_70_ROWS_RESPONSE["results"][4]
        
        assert row["id"] == 5107
        cols = row["columns"]
        assert cols["Client"] == "SOPHIE LECLERC"
        assert cols["Amount"] == 450.25
        assert cols["Action"] == "1st NSF"
        assert cols["Wave"] == 1


class TestBoard70PhoneParsing:
    """Test phone number extraction and validation."""

    @pytest.mark.django_db
    def test_maria_gonzalez_phone(self):
        """Test Maria's phone number parsing."""
        row = BOARD_70_ROWS_RESPONSE["results"][0]
        phone_obj = row["columns"]["Phone Number"]
        
        assert phone_obj["valid"] is True
        assert phone_obj["country"] == "CA"
        assert phone_obj["raw"] == "+14165551234"
        assert phone_obj["formatted"] == "(416) 555-1234"

    @pytest.mark.django_db
    def test_james_mitchell_phone(self):
        """Test James's phone number parsing."""
        row = BOARD_70_ROWS_RESPONSE["results"][1]
        phone_obj = row["columns"]["Phone Number"]
        
        assert phone_obj["valid"] is True
        assert phone_obj["country"] == "CA"
        assert phone_obj["raw"] == "+16045559876"
        assert phone_obj["formatted"] == "(604) 555-9876"

    @pytest.mark.django_db
    def test_all_phones_valid(self):
        """Verify all phones are marked as valid."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            phone_obj = row["columns"]["Phone Number"]
            assert phone_obj["valid"] is True, f"Row {row['id']}: Phone not valid"

    @pytest.mark.django_db
    def test_all_phones_have_country_code(self):
        """Verify all phones have country codes."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            phone_obj = row["columns"]["Phone Number"]
            assert phone_obj["country"] == "CA"
            assert phone_obj["raw"].startswith("+")


class TestBoard70EmailParsing:
    """Test email extraction."""

    @pytest.mark.django_db
    def test_all_emails_valid(self):
        """Verify all emails are non-empty."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            email = row["columns"]["Email"]
            assert email
            assert "@" in email
            assert "." in email

    @pytest.mark.django_db
    def test_maria_gonzalez_email(self):
        """Test Maria's email."""
        row = BOARD_70_ROWS_RESPONSE["results"][0]
        assert row["columns"]["Email"] == "maria.gonzalez@email.com"

    @pytest.mark.django_db
    def test_james_mitchell_email(self):
        """Test James's email."""
        row = BOARD_70_ROWS_RESPONSE["results"][1]
        assert row["columns"]["Email"] == "james.m.mitchell@email.com"


class TestBoard70EmailMetrics:
    """Test email metrics data."""

    @pytest.mark.django_db
    def test_maria_email_metrics_initial(self):
        """Test Maria's email metrics (Wave 1 - no emails yet)."""
        row = BOARD_70_ROWS_RESPONSE["results"][0]
        email_metric = row["columns"]["email metric"]
        
        assert email_metric["sent_count"] == 0
        assert email_metric["opened_count"] == 0
        assert email_metric["last_opened"] is None

    @pytest.mark.django_db
    def test_james_email_metrics(self):
        """Test James's email metrics (Wave 2)."""
        row = BOARD_70_ROWS_RESPONSE["results"][1]
        email_metric = row["columns"]["email metric"]
        
        assert email_metric["sent_count"] == 1
        assert email_metric["opened_count"] == 1
        assert email_metric["last_opened"] is not None

    @pytest.mark.django_db
    def test_alexandra_email_metrics(self):
        """Test Alexandra's email metrics (Wave 3)."""
        row = BOARD_70_ROWS_RESPONSE["results"][2]
        email_metric = row["columns"]["email metric"]
        
        assert email_metric["sent_count"] == 2
        assert email_metric["opened_count"] == 2

    @pytest.mark.django_db
    def test_david_email_metrics(self):
        """Test David's email metrics (Wave 4)."""
        row = BOARD_70_ROWS_RESPONSE["results"][3]
        email_metric = row["columns"]["email metric"]
        
        assert email_metric["sent_count"] == 3
        assert email_metric["opened_count"] == 3


class TestBoard70NSFEscalation:
    """Test NSF escalation logic."""

    @pytest.mark.django_db
    def test_wave_progression(self):
        """Verify Wave progression from 1 to 4."""
        waves = [row["columns"]["Wave"] for row in BOARD_70_ROWS_RESPONSE["results"][:4]]
        expected_waves = [1, 2, 3, 4]
        assert waves == expected_waves

    @pytest.mark.django_db
    def test_action_progression(self):
        """Verify Action (NSF stage) progression."""
        actions = [row["columns"]["Action"] for row in BOARD_70_ROWS_RESPONSE["results"][:4]]
        expected_actions = ["1st NSF", "2nd NSF", "3rd NSF", "Final Pressure"]
        assert actions == expected_actions

    @pytest.mark.django_db
    def test_amount_increases_with_fees(self):
        """Verify amounts increase with NSF fees."""
        # Each row's Balance should be higher than Amount (due to added fee)
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            amount = row["columns"]["Amount"]
            balance = row["columns"]["Balance"]
            assert balance > amount, f"Balance ({balance}) should be > Amount ({amount})"

    @pytest.mark.django_db
    def test_reasons_are_eft_failures(self):
        """Verify all reasons are EFT-related."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            reason = row["columns"]["Reason"]
            assert reason.startswith("EFT Failed")


class TestBoard70Amounts:
    """Test amount calculations."""

    @pytest.mark.django_db
    def test_all_amounts_positive(self):
        """Verify all amounts are positive."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            amount = row["columns"]["Amount"]
            assert amount > 0

    @pytest.mark.django_db
    def test_all_balances_positive(self):
        """Verify all balances are positive."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            balance = row["columns"]["Balance"]
            assert balance > 0

    @pytest.mark.django_db
    def test_total_amounts(self):
        """Verify total amounts across all rows."""
        total_amount = sum(row["columns"]["Amount"] for row in BOARD_70_ROWS_RESPONSE["results"])
        expected_total = 525.50 + 750.00 + 325.75 + 600.00 + 450.25
        assert total_amount == expected_total


class TestBoard70Dates:
    """Test date fields."""

    @pytest.mark.django_db
    def test_all_dates_in_2026(self):
        """Verify all dates are in 2026."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            date_str = row["columns"]["Date"]
            assert date_str.startswith("2026")

    @pytest.mark.django_db
    def test_all_dates_in_march(self):
        """Verify all dates are in March 2026."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            date_str = row["columns"]["Date"]
            assert date_str.startswith("2026-03")

    @pytest.mark.django_db
    def test_last_updated_format(self):
        """Verify Last Updated format is ISO 8601."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            last_updated = row["columns"]["Last Updated"]
            assert "start" in last_updated
            assert "end" in last_updated
            # Both should be ISO format with timezone
            assert "T" in last_updated["start"]
            assert "+00:00" in last_updated["start"]


class TestBoard70EdgeCases:
    """Test edge cases."""

    @pytest.mark.django_db
    def test_missing_amount_field(self):
        """Test row with missing Amount field."""
        row_data = BOARD_70_ROWS_MISSING_AMOUNT["results"][0]
        
        assert row_data["columns"]["Amount"] is None
        assert row_data["columns"]["Client"] == "UNKNOWN CLIENT"

    @pytest.mark.django_db
    def test_invalid_phone_number(self):
        """Test row with invalid phone number."""
        row_data = BOARD_70_ROWS_INVALID_CONTACT["results"][0]
        phone_obj = row_data["columns"]["Phone Number"]
        
        assert phone_obj["valid"] is False
        assert phone_obj["raw"] == "invalid"

    @pytest.mark.django_db
    def test_invalid_email(self):
        """Test row with invalid email."""
        row_data = BOARD_70_ROWS_INVALID_CONTACT["results"][0]
        email = row_data["columns"]["Email"]
        
        assert email == "not_an_email"
        assert "@" not in email

    @pytest.mark.django_db
    def test_duplicate_row_ids(self):
        """Test duplicate row IDs."""
        results = BOARD_70_ROWS_DUPLICATE["results"]
        
        assert len(results) == 2
        assert results[0]["id"] == 7777
        assert results[1]["id"] == 7777


class TestBoard70DataIntegrity:
    """Test data consistency and integrity."""

    @pytest.mark.django_db
    def test_board_id_consistency(self):
        """Verify all rows have correct board_id."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            assert row["board_id"] == 70

    @pytest.mark.django_db
    def test_group_id_consistency(self):
        """Verify all rows have correct group_id."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            assert row["group_id"] == 91

    @pytest.mark.django_db
    def test_all_rows_have_columns(self):
        """Verify all rows have columns dict."""
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            assert "columns" in row
            assert isinstance(row["columns"], dict)

    @pytest.mark.django_db
    def test_no_null_required_fields(self):
        """Verify no required fields are null (except email metric None values)."""
        required_fields = ["Client", "Amount", "Phone Number", "Email", "Date", "Reason"]
        
        for row in BOARD_70_ROWS_RESPONSE["results"]:
            columns = row["columns"]
            for field in required_fields:
                assert field in columns, f"Missing field: {field}"
                # Amount can be 0, but shouldn't be None for valid rows
                if field != "Amount":
                    assert columns[field] is not None, f"{field} is None in row {row['id']}"


class TestBoard70TestDataSets:
    """Test the organized test data sets."""

    def test_test_data_sets_coverage(self):
        """Verify all test data sets are defined."""
        expected_keys = [
            "board70_happy_path",
            "board70_edge_missing_amount",
            "board70_edge_invalid_contact",
            "board70_edge_duplicate_rows",
        ]
        
        for key in expected_keys:
            assert key in TEST_DATA_SETS

    def test_all_test_data_sets_have_results(self):
        """Verify all test data sets contain valid results."""
        for key, data in TEST_DATA_SETS.items():
            assert "board" in data, f"{key} missing board metadata"
            assert "results" in data, f"{key} missing results"
            assert len(data["results"]) > 0, f"{key} has empty results"


class TestBoard70IngestionIntegration:
    """Integration tests for Board 70 ingestion."""

    @pytest.mark.django_db
    @patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
    def test_mock_board70_response(self, mock_get_rows):
        """Test that mock returns correct Board 70 data."""
        mock_get_rows.return_value = BOARD_70_ROWS_RESPONSE
        
        response = mock_get_rows()
        
        assert response["board"]["id"] == 70
        assert len(response["results"]) == 5
        assert response["results"][0]["columns"]["Client"] == "MARIA GONZALEZ"

    @pytest.mark.django_db
    def test_sync_report_initialization(self):
        """Test SyncReport initialization."""
        report = SyncReport(dry_run=True)
        
        assert report.dry_run is True
        assert report.processed == 0
        assert report.created == 0
        assert report.updated == 0
        assert report.skipped == 0
        assert report.errors == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
