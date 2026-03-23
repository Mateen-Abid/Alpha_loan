"""
CRM Ingestion Dummy Data - Test Runner & Documentation

This module provides utilities to run and validate the CRM ingestion tests.
Use this to verify the ingestion pipeline works correctly with the dummy data.

USAGE:
  pytest tests/test_crm_ingestion_dummy_data.py -v
  pytest tests/test_crm_ingestion_dummy_data.py::TestBoard70DailyRejectsIngestion -v
  pytest tests/test_crm_ingestion_dummy_data.py -k "board70" -v
"""

import sys
from pathlib import Path
from decimal import Decimal
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

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


class CRMTestDataValidator:
    """Validate test data integrity before running tests."""

    @staticmethod
    def validate_board_response_structure(response: Dict[str, Any], board_id: int) -> bool:
        """Validate board response structure."""
        assert "board" in response, "Missing 'board' key"
        assert "results" in response, "Missing 'results' key"
        assert response["board"]["id"] == board_id, f"Board ID mismatch: expected {board_id}"
        assert isinstance(response["results"], list), "Results should be a list"
        assert len(response["results"]) > 0, "Results should not be empty"
        return True

    @staticmethod
    def validate_row_structure(row: Dict[str, Any], board_id: int) -> bool:
        """Validate individual row structure."""
        required_fields = ["id", "board_id", "group_id", "columns"]
        for field in required_fields:
            assert field in row, f"Missing '{field}' in row"
        
        assert row["board_id"] == board_id, f"Row board_id mismatch"
        assert isinstance(row["columns"], dict), "Columns should be a dict"
        return True

    @staticmethod
    def validate_columns(columns: Dict[str, Any], required_fields: List[str]) -> bool:
        """Validate required fields in columns."""
        for field in required_fields:
            assert field in columns, f"Missing required column: {field}"
        return True

    @staticmethod
    def print_validation_summary():
        """Print summary of validation results."""
        print("\n" + "=" * 80)
        print("CRM TEST DATA VALIDATION SUMMARY")
        print("=" * 80)
        
        tests = [
            ("Board 70 Structure", lambda: CRMTestDataValidator.validate_board_response_structure(BOARD_70_ROWS_RESPONSE, 70)),
            ("Board 71 Structure", lambda: CRMTestDataValidator.validate_board_response_structure(BOARD_71_ROWS_RESPONSE, 71)),
            ("Board 73 Structure", lambda: CRMTestDataValidator.validate_board_response_structure(BOARD_73_ROWS_RESPONSE, 73)),
            ("Board 74 Structure", lambda: CRMTestDataValidator.validate_board_response_structure(BOARD_74_ROWS_RESPONSE, 74)),
            ("Board 70 Rows", lambda: all(CRMTestDataValidator.validate_row_structure(r, 70) for r in BOARD_70_ROWS_RESPONSE["results"])),
            ("Board 71 Rows", lambda: all(CRMTestDataValidator.validate_row_structure(r, 71) for r in BOARD_71_ROWS_RESPONSE["results"])),
            ("Board 70 Required Fields", lambda: CRMTestDataValidator.validate_columns(BOARD_70_ROWS_RESPONSE["results"][0]["columns"], ["Client", "Amount", "Phone Number", "Email"])),
            ("Test Data Sets", lambda: len(TEST_DATA_SETS) == 7),
        ]
        
        passed = 0
        failed = 0
        
        for test_name, test_func in tests:
            try:
                result = test_func()
                status = "✓ PASS" if result else "✗ FAIL"
                passed += 1 if result else 0
                failed += 0 if result else 1
                print(f"  {status:8} | {test_name}")
            except AssertionError as e:
                print(f"  ✗ FAIL   | {test_name}: {str(e)}")
                failed += 1
            except Exception as e:
                print(f"  ✗ ERROR  | {test_name}: {str(e)}")
                failed += 1
        
        print("=" * 80)
        print(f"Total: {passed} passed, {failed} failed")
        print("=" * 80 + "\n")
        
        return failed == 0


class CRMTestDataSummary:
    """Generate summary information about test data."""

    @staticmethod
    def get_board_summary() -> str:
        """Get summary of all boards."""
        summary = "\nCRM TEST DATA - BOARD SUMMARY\n"
        summary += "=" * 80 + "\n"
        
        boards_info = [
            (70, "Daily Rejects", BOARD_70_ROWS_RESPONSE),
            (71, "E-Transfer", BOARD_71_ROWS_RESPONSE),
            (73, "E-Transfer Agreements", BOARD_73_ROWS_RESPONSE),
            (74, "Received E-Transfer", BOARD_74_ROWS_RESPONSE),
        ]
        
        for board_id, board_name, response in boards_info:
            rows = response["results"]
            summary += f"\nBoard {board_id}: {board_name}\n"
            summary += f"  Total Rows: {len(rows)}\n"
            
            if rows:
                sample_row = rows[0]
                if "Phone Number" in sample_row["columns"]:
                    summary += f"  Sample Phone: {sample_row['columns']['Phone Number'].get('formatted', 'N/A')}\n"
                if "Amount" in sample_row["columns"]:
                    summary += f"  Sample Amount: ${sample_row['columns']['Amount']}\n"
        
        summary += "\n" + "=" * 80 + "\n"
        return summary

    @staticmethod
    def get_row_statistics() -> str:
        """Get statistics about rows."""
        stats = "\nCRM TEST DATA - ROW STATISTICS\n"
        stats += "=" * 80 + "\n"
        
        boards = [
            ("Board 70 - Daily Rejects", BOARD_70_ROWS_RESPONSE),
            ("Board 71 - E-Transfer", BOARD_71_ROWS_RESPONSE),
            ("Board 73 - E-Transfer Agreements", BOARD_73_ROWS_RESPONSE),
            ("Board 74 - Received E-Transfer", BOARD_74_ROWS_RESPONSE),
        ]
        
        for board_name, response in boards:
            rows = response["results"]
            
            # Calculate total amounts
            total_amount = Decimal(0)
            total_balance = Decimal(0)
            
            for row in rows:
                cols = row["columns"]
                if "Amount" in cols and isinstance(cols["Amount"], (int, float)):
                    total_amount += Decimal(str(cols["Amount"]))
                if "Balance" in cols and isinstance(cols["Balance"], (int, float)):
                    total_balance += Decimal(str(cols["Balance"]))
            
            stats += f"\n{board_name}\n"
            stats += f"  Row Count: {len(rows)}\n"
            stats += f"  Total Amount: ${total_amount:.2f}\n"
            stats += f"  Total Balance: ${total_balance:.2f}\n"
        
        stats += "\n" + "=" * 80 + "\n"
        return stats

    @staticmethod
    def get_edge_cases_summary() -> str:
        """Get summary of edge case scenarios."""
        summary = "\nCRM TEST DATA - EDGE CASES\n"
        summary += "=" * 80 + "\n"
        
        edge_cases = [
            ("Missing Amount", BOARD_70_ROWS_MISSING_AMOUNT),
            ("Invalid Contact", BOARD_70_ROWS_INVALID_CONTACT),
            ("Duplicate Rows", BOARD_70_ROWS_DUPLICATE),
        ]
        
        for case_name, response in edge_cases:
            rows = response["results"]
            summary += f"\n{case_name}:\n"
            summary += f"  Rows: {len(rows)}\n"
            
            for row in rows:
                cols = row["columns"]
                summary += f"  - Row {row['id']}: {cols.get('Client', 'Unknown')}\n"
                
                if "Amount" in cols:
                    summary += f"    Amount: {cols['Amount']}\n"
                
                if "Phone Number" in cols and isinstance(cols["Phone Number"], dict):
                    summary += f"    Phone Valid: {cols['Phone Number'].get('valid', False)}\n"
        
        summary += "\n" + "=" * 80 + "\n"
        return summary


def run_validation():
    """Run data validation and print summaries."""
    print("\nStarting CRM Test Data Validation...\n")
    
    # Validate structure
    is_valid = CRMTestDataValidator.print_validation_summary()
    
    if not is_valid:
        print("❌ Validation failed! Please check the test data.")
        return False
    
    # Print summary information
    print(CRMTestDataSummary.get_board_summary())
    print(CRMTestDataSummary.get_row_statistics())
    print(CRMTestDataSummary.get_edge_cases_summary())
    
    print("✅ All validations passed!\n")
    print("Ready to run tests with:")
    print("  pytest tests/test_crm_ingestion_dummy_data.py -v\n")
    
    return True


def test_data_quick_reference():
    """Print quick reference for test data usage."""
    reference = """
QUICK REFERENCE - CRM TEST DATA

1. BOARD 70 - DAILY REJECTS
   - Use: BOARD_70_ROWS_RESPONSE
   - Contains: 5 rows with NSF fee escalation (Wave 1-4)
   - Test: Verify NSF fee logic and escalation workflow
   - Scenario: Initial EFT failure -> multiple NSF fees -> final pressure

2. BOARD 71 - E-TRANSFER
   - Use: BOARD_71_ROWS_RESPONSE
   - Contains: 4 rows across different due date groups
   - Test: Verify due date-based routing (Overdue, Today, Tomorrow, Future)
   - Scenario: Following up on e-transfer payments with different timelines

3. BOARD 73 - E-TRANSFER AGREEMENTS
   - Use: BOARD_73_ROWS_RESPONSE
   - Contains: 3 rows with payment agreements
   - Test: Verify agreement tracking and amounts
   - Scenario: Recording agreed-upon e-transfer payment plans

4. BOARD 74 - RECEIVED E-TRANSFER
   - Use: BOARD_74_ROWS_RESPONSE
   - Contains: 3 rows with received payments (Balance = 0)
   - Test: Verify payment receipt logging
   - Scenario: Successfully received e-transfers and account clearing

EDGE CASES

1. MISSING AMOUNT
   - File: BOARD_70_ROWS_MISSING_AMOUNT
   - Test: Should trigger MISSING_DUE_AMOUNT skip
   - Expected: Row skipped, not ingested

2. INVALID CONTACT
   - File: BOARD_70_ROWS_INVALID_CONTACT
   - Test: Should use fallback phone/email
   - Expected: Row ingested with sanitized contact info

3. DUPLICATE ROWS
   - File: BOARD_70_ROWS_DUPLICATE
   - Test: Should recognize duplicate row_id
   - Expected: Idempotent handling (update, not insert)

HOW TO USE IN TESTS

From test file:
    from tests.fixtures.crm_test_data import BOARD_70_ROWS_RESPONSE

Mock the client call:
    @patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
    def test_something(self, mock_get_rows):
        mock_get_rows.return_value = BOARD_70_ROWS_RESPONSE
        # Now test your code...

Run specific test:
    pytest tests/test_crm_ingestion_dummy_data.py::TestBoard70DailyRejectsIngestion -v
    """
    return reference


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CRM Test Data Validator")
    parser.add_argument("--validate", action="store_true", help="Run data validation")
    parser.add_argument("--summary", action="store_true", help="Print data summary")
    parser.add_argument("--reference", action="store_true", help="Print quick reference")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    
    args = parser.parse_args()
    
    if args.validate or args.all:
        run_validation()
    
    if args.summary or args.all:
        print(CRMTestDataSummary.get_board_summary())
        print(CRMTestDataSummary.get_row_statistics())
        print(CRMTestDataSummary.get_edge_cases_summary())
    
    if args.reference or args.all or (not args.validate and not args.summary and not args.reference):
        print(test_data_quick_reference())
