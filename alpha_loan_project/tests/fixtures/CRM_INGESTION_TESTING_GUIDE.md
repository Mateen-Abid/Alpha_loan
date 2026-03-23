# CRM Ingestion Testing Guide - Dummy Data

## Overview

This directory contains comprehensive **dummy test data** that mirrors the real iCollector Partner Gateway API responses. These fixtures are designed to test your CRM board ingestion pipeline without modifying any code.

**Important:** This is TESTING DATA ONLY. No ingestion code has been changed.

---

## Files in This Directory

### 1. `crm_test_data.py`
Contains all dummy data organized by board and scenario:
- **CRM_BOARDS_RESPONSE**: Metadata for all 4 CRM boards
- **BOARD_70_ROWS_RESPONSE**: Daily Rejects board (NSF fee scenarios)
- **BOARD_71_ROWS_RESPONSE**: E-Transfer board (due date handling)
- **BOARD_73_ROWS_RESPONSE**: E-Transfer Agreements board
- **BOARD_74_ROWS_RESPONSE**: Received E-Transfer board (payment logging)
- **Edge case data**: Missing amounts, invalid contacts, duplicates

### 2. `test_crm_ingestion_dummy_data.py`
Comprehensive pytest test suite with 50+ test cases:
- Board metadata validation
- Row parsing tests (all 4 boards)
- Phone/email extraction
- Email metrics parsing
- Escalation path testing
- Edge case handling
- Data integrity checks

### 3. `crm_test_runner.py`
Test utilities and validation tools:
- Data structure validator
- Summary statistics generator
- Quick reference guide
- Command-line utilities

---

## Quick Start

### 1. Validate Test Data
```bash
# Run validation to ensure data integrity
python tests/fixtures/crm_test_runner.py --validate

# Expected output:
#   ✓ PASS | Board 70 Structure
#   ✓ PASS | Board 71 Structure
#   ✓ PASS | Board 73 Structure
#   ✓ PASS | Board 74 Structure
#   ✓ PASS | All tests passed!
```

### 2. View Test Summary
```bash
python tests/fixtures/crm_test_runner.py --summary

# Shows:
#   - Row counts per board
#   - Total amounts
#   - Total balances
#   - Edge case scenarios
```

### 3. Run All Tests
```bash
# Run entire test suite
pytest tests/test_crm_ingestion_dummy_data.py -v

# Output shows:
#   test_board70_basic_row_ingestion PASSED
#   test_board70_phone_parsing PASSED
#   test_board71_overdue_group PASSED
#   ... (50+ tests)
```

### 4. Run Specific Test Group
```bash
# Test only Board 70 parsing
pytest tests/test_crm_ingestion_dummy_data.py::TestBoard70DailyRejectsIngestion -v

# Test only edge cases
pytest tests/test_crm_ingestion_dummy_data.py::TestEdgeCases -v

# Test only data integrity
pytest tests/test_crm_ingestion_dummy_data.py::TestDataIntegrity -v
```

### 5. Run Tests with Keywords
```bash
# Test all board70 related tests
pytest tests/test_crm_ingestion_dummy_data.py -k "board70" -v

# Test all phone-related tests
pytest tests/test_crm_ingestion_dummy_data.py -k "phone" -v

# Test all email-related tests
pytest tests/test_crm_ingestion_dummy_data.py -k "email" -v
```

---

## Test Data Organization

### Board 70 - Daily Rejects (NSF Fee Scenarios)
**Purpose:** Track daily EFT failures and NSF fee progression

**5 Sample Rows:**
```
Row 1: Wave 1 - Initial NSF (Amount: $525.50)
Row 2: Wave 2 - 2nd NSF (Amount: $750.00)
Row 3: Wave 3 - 3rd NSF (Amount: $325.75)
Row 4: Wave 4 - Final Pressure (Amount: $600.00)
Row 5: Fresh Wave 1 - New case (Amount: $450.25)
```

**Key Fields:**
- `Reason`: NSF failure reason (Insufficient Funds, Stop Payment, Account Closed)
- `Amount`: Failed payment amount
- `Action`: Treatment stage (1st NSF, 2nd NSF, 3rd NSF, Final Pressure)
- `Wave`: Escalation level (1-4)

**Test Scenarios:**
- ✓ NSF fee escalation logic
- ✓ Wave progression
- ✓ Contact information extraction
- ✓ Email metrics tracking

### Board 71 - E-Transfer (Due Date Handling)
**Purpose:** Manage e-transfer payments across date groups

**4 Sample Rows (Different Groups):**
```
Group 93 (Overdue):   Robert Patterson - Due 2026-03-10 ($300.00)
Group 94 (Today):     Jennifer Torres  - Due 2026-03-20 ($500.00)
Group 95 (Tomorrow):  Michael Soto     - Due 2026-03-21 ($250.00)
Group 96 (Future):    Patrick Ryan     - Due 2026-04-10 ($400.00)
```

**Key Fields:**
- `Due Date`: Original due date
- `Next Due Date`: Next scheduled payment date
- `Frequency`: Payment frequency (Weekly, Bi-weekly, Monthly)
- `Action`: Required action (Follow Up, Send Today, Send Tomorrow, Schedule)

**Test Scenarios:**
- ✓ Group-based routing (Overdue/Today/Tomorrow/Future)
- ✓ Due date comparison logic
- ✓ Frequency-based scheduling

### Board 73 - E-Transfer Agreements (Agreement Tracking)
**Purpose:** Track agreed-upon payment arrangements

**3 Sample Rows:**
```
Lisa Wang       - $150.00 (2026-03-01)
Thomas Bernard  - $225.00 (2026-02-28)
Yasmin Patel    - $175.50 (2026-03-05)
```

**Test Scenarios:**
- ✓ Agreement amount recording
- ✓ Agreement date tracking

### Board 74 - Received E-Transfer (Payment Receipt)
**Purpose:** Log successfully received payments

**3 Sample Rows (All with Balance = $0.00):**
```
Rachel Morrison       - $300.00 received (2026-03-18)
Christopher Ellis    - $500.00 received (2026-03-17)
Nina Santos         - $250.00 received (2026-03-19)
```

**Test Scenarios:**
- ✓ Payment receipt logging
- ✓ Balance clearing verification

---

## Edge Cases Included

### 1. Missing Amount (Should Skip)
```python
BOARD_70_ROWS_MISSING_AMOUNT
- Row ID: 9999
- Amount: None  # Missing!
- Expected: Row skipped with MISSING_DUE_AMOUNT
```

**Test:** Verify ingestion service skips rows without amounts

### 2. Invalid Contact Info (Should Use Fallback)
```python
BOARD_70_ROWS_INVALID_CONTACT
- Row ID: 8888
- Phone: "invalid" (not formatted)
- Email: "not_an_email" (missing @)
- Expected: Ingestion uses fallback phone
```

**Test:** Verify contact sanitization logic

### 3. Duplicate Row IDs (Idempotency)
```python
BOARD_70_ROWS_DUPLICATE
- Both rows: ID 7777
- Same client, different "Last Updated"
- Expected: Idempotent update, not duplicate insert
```

**Test:** Verify duplicate handling and idempotency

---

## How to Use with Your Ingestion Code

### Mock External API Calls

```python
from unittest.mock import patch
from tests.fixtures.crm_test_data import BOARD_70_ROWS_RESPONSE

@pytest.mark.django_db
@patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
def test_board70_ingestion(self, mock_get_rows):
    # Mock the API to return dummy data
    mock_get_rows.return_value = BOARD_70_ROWS_RESPONSE
    
    # Now test your ingestion service
    service = CRMIngestService()
    report = service.sync(board_ids=[70], dry_run=False)
    
    # Verify results
    assert report["created"] == 5
    assert report["errors"] == 0
```

### Test Specific Board
```python
@patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
def test_board71_etransfer(self, mock_get_rows):
    mock_get_rows.return_value = BOARD_71_ROWS_RESPONSE
    
    service = CRMIngestService()
    report = service.sync(board_ids=[71], dry_run=False)
    
    # Verify group distribution
    assert report["per_group_distribution"]["71:93"] == 1  # Overdue
    assert report["per_group_distribution"]["71:94"] == 1  # Today
    assert report["per_group_distribution"]["71:95"] == 1  # Tomorrow
    assert report["per_group_distribution"]["71:96"] == 1  # Future
```

### Test All Boards
```python
@patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
def test_all_boards_ingestion(self, mock_get_rows):
    responses = {
        (70, None): BOARD_70_ROWS_RESPONSE,
        (71, None): BOARD_71_ROWS_RESPONSE,
        (73, None): BOARD_73_ROWS_RESPONSE,
        (74, None): BOARD_74_ROWS_RESPONSE,
    }
    
    def side_effect(board_id, **kwargs):
        key = (board_id, kwargs.get("group_id"))
        return responses.get(key, {"results": []})
    
    mock_get_rows.side_effect = side_effect
    
    service = CRMIngestService()
    report = service.sync(board_ids=[70, 71, 73, 74], dry_run=False)
    
    # Verify all boards processed
    assert report["per_board_distribution"]["70"] == 5
    assert report["per_board_distribution"]["71"] == 4
    assert report["per_board_distribution"]["73"] == 3
    assert report["per_board_distribution"]["74"] == 3
```

---

## Data Structure Reference

### Row Structure
```python
{
    "id": 5103,                    # Unique row ID
    "board_id": 70,                # Board identifier
    "group_id": 91,                # Group within board
    "position": 15,                # Display position
    "columns": {
        "Client": "MARIA GONZALEZ",
        "Phone Number": {
            "raw": "+14165551234",
            "valid": True,
            "country": "CA",
            "formatted": "(416) 555-1234"
        },
        "Email": "maria.gonzalez@email.com",
        "Amount": 525.50,
        "Balance": 575.50,
        "Date": "2026-03-20",
        "Reason": "EFT Failed Insufficient Funds",
        "Action": "1st NSF",
        "Last Updated": {
            "start": "2026-03-20T10:30:00.000000+00:00",
            "end": "2026-03-20T10:30:00.000000+00:00"
        },
        # ... more fields
    }
}
```

### Response Structure
```python
{
    "board": {
        "id": 70,
        "name": "Daily Rejects"
    },
    "count": 100,           # Rows in this page
    "total": 1630,          # Total rows across all pages
    "limit": 100,           # Page size
    "offset": 0,            # Pagination offset
    "results": [
        # Array of row objects
    ]
}
```

---

## Verification Checklist

After running tests, verify:

- [ ] **All 5 Board 70 rows** parse correctly with NSF amounts
- [ ] **All 4 Board 71 rows** route to correct groups (Overdue/Today/Tomorrow/Future)
- [ ] **All 3 Board 73 rows** record agreement amounts
- [ ] **All 3 Board 74 rows** show zero balance after payment
- [ ] **Phone numbers** parse with country codes and formats
- [ ] **Email metrics** are captured (sent_count, opened_count)
- [ ] **Missing Amount** edge case skips row correctly
- [ ] **Invalid Contact** edge case uses fallback phone
- [ ] **Duplicate Row IDs** are handled idempotently
- [ ] **All dates** are in 2026 format
- [ ] **All amounts** are non-negative decimals

---

## Next Steps

### After Ingestion Testing Passes:

1. **Webhook Ingestion Testing** - Test webhook payload processing
   - SMS inbound webhook
   - Email inbound webhook
   - CRM webhook for new failures

2. **State Machine Testing** - Test workflow transitions
   - NSF escalation path (STEP_1 → STEP_4)
   - Intent-based transitions

3. **SMS Communication Testing** - Test outbound message sending
   - Initial SMS to borrowers
   - Follow-up messages
   - Escalation messages

4. **Integration Testing** - Full end-to-end flow
   - Ingest → Parse → Update → Send SMS

---

## Troubleshooting

### Tests Failing with "Import Error"
```bash
# Make sure you're in the project root
cd alpha_loan_project

# Run with python path set
PYTHONPATH=. pytest tests/test_crm_ingestion_dummy_data.py -v
```

### Tests Timing Out
```bash
# Increase timeout
pytest tests/test_crm_ingestion_dummy_data.py -v --timeout=30
```

### Mock Not Working
```python
# Make sure patch path is correct
@patch('apps.core.services.ingest_service.ICollectorClient.get_rows')
# NOT: @patch('apps.core.integrations.icollector_client.ICollectorClient.get_rows')
```

---

## Support & Questions

For questions about the test data, consult:
- `crm_test_data.py` - Data definitions
- `test_crm_ingestion_dummy_data.py` - Test implementations
- `crm_test_runner.py` - Utilities and validation

All data mirrors real API responses from iCollector Partner Gateway.

---

**Last Updated:** March 23, 2026  
**Test Data Status:** ✅ Validated and Ready for Use
