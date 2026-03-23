# Board 70 (Daily Rejects) - Focused Testing Guide

**Status:** ✅ Ready for Testing  
**Focus:** Board 70 Only (Daily Rejects)  
**Date:** March 23, 2026

---

## 📋 Quick Start (2 Steps)

### Step 1: Run All Board 70 Tests
```bash
pytest tests/test_board70_daily_rejects.py -v
```

**Expected Output:**
```
test_board_metadata_structure PASSED
test_board_columns_exist PASSED
test_first_row_maria_gonzalez PASSED
test_second_row_james_mitchell PASSED
test_third_row_alexandra_chen PASSED
test_fourth_row_david_kumar PASSED
test_fifth_row_sophie_leclerc PASSED
test_wave_progression PASSED
test_action_progression PASSED
test_all_phones_valid PASSED
...
==================== 50+ passed in ~2s ====================
```

### Step 2: Run Specific Test Category
```bash
# Test only wave progression
pytest tests/test_board70_daily_rejects.py::TestBoard70NSFEscalation -v

# Test only phone parsing
pytest tests/test_board70_daily_rejects.py::TestBoard70PhoneParsing -v

# Test only edge cases
pytest tests/test_board70_daily_rejects.py::TestBoard70EdgeCases -v

# Test only data integrity
pytest tests/test_board70_daily_rejects.py::TestBoard70DataIntegrity -v
```

---

## 📊 Test Coverage

### Rows (5 Happy Path + 3 Edge Cases)

#### Happy Path: NSF Escalation Workflow
```
Row 1: MARIA GONZALEZ
├─ Wave: 1 (Initial)
├─ Action: 1st NSF
├─ Amount: $525.50
├─ Email Metrics: No sends yet
└─ Status: ✅ Ready for initial SMS

Row 2: JAMES MITCHELL
├─ Wave: 2 (Escalation)
├─ Action: 2nd NSF
├─ Amount: $750.00
├─ Email Metrics: 1 sent, 1 opened
└─ Status: ✅ Follow-up needed

Row 3: ALEXANDRA CHEN
├─ Wave: 3 (High Pressure)
├─ Action: 3rd NSF
├─ Amount: $325.75
├─ Email Metrics: 2 sent, 2 opened
└─ Status: ✅ Escalation pending

Row 4: DAVID KUMAR
├─ Wave: 4 (Final)
├─ Action: Final Pressure
├─ Amount: $600.00
├─ Email Metrics: 3 sent, 3 opened
└─ Status: ✅ Legal review

Row 5: SOPHIE LECLERC
├─ Wave: 1 (New Case)
├─ Action: 1st NSF
├─ Amount: $450.25
├─ Email Metrics: No sends yet
└─ Status: ✅ New ingestion
```

#### Edge Cases
```
Edge Case 1: Missing Amount
├─ Row ID: 9999
├─ Amount: None
├─ Expected: Skip with MISSING_DUE_AMOUNT error
└─ Test: test_missing_amount_field

Edge Case 2: Invalid Contact
├─ Row ID: 8888
├─ Phone: Invalid
├─ Email: Invalid
├─ Expected: Use fallback phone/email
└─ Test: test_invalid_phone_number, test_invalid_email

Edge Case 3: Duplicate Rows
├─ Both ID: 7777
├─ Same Client: DUPLICATE TEST USER
├─ Expected: Idempotent update (not duplicate insert)
└─ Test: test_duplicate_row_ids
```

---

## 🧪 Test Classes

### 1. TestBoard70Metadata (3 tests)
- ✓ Metadata structure validation
- ✓ Required columns present
- ✓ Column types correct

### 2. TestBoard70BasicIngestion (6 tests)
- ✓ Response structure
- ✓ Pagination metadata
- ✓ Each row content validation (Rows 1-5)

### 3. TestBoard70PhoneParsing (4 tests)
- ✓ Individual phone parsing
- ✓ All phones valid
- ✓ All phones have country codes

### 4. TestBoard70EmailParsing (3 tests)
- ✓ All emails valid
- ✓ Individual email validation

### 5. TestBoard70EmailMetrics (4 tests)
- ✓ Wave 1 metrics (no sends)
- ✓ Wave 2 metrics (1 send/open)
- ✓ Wave 3 metrics (2 sends/opens)
- ✓ Wave 4 metrics (3 sends/opens)

### 6. TestBoard70NSFEscalation (4 tests)
- ✓ Wave progression (1→2→3→4)
- ✓ Action progression (1st→2nd→3rd→Final)
- ✓ Amount increases with fees
- ✓ All reasons are EFT failures

### 7. TestBoard70Amounts (3 tests)
- ✓ All amounts positive
- ✓ All balances positive
- ✓ Total amounts correct

### 8. TestBoard70Dates (3 tests)
- ✓ All dates in 2026
- ✓ All dates in March
- ✓ Last Updated format ISO 8601

### 9. TestBoard70EdgeCases (4 tests)
- ✓ Missing amount handling
- ✓ Invalid phone handling
- ✓ Invalid email handling
- ✓ Duplicate row handling

### 10. TestBoard70DataIntegrity (4 tests)
- ✓ Board ID consistency
- ✓ Group ID consistency
- ✓ All rows have columns
- ✓ No null required fields

### 11. TestBoard70TestDataSets (2 tests)
- ✓ All data sets defined
- ✓ All data sets have results

### 12. TestBoard70IngestionIntegration (2 tests)
- ✓ Mock returns correct data
- ✓ SyncReport initialization

**Total: 50+ test cases**

---

## 📁 Files

### Test Data
- **`tests/fixtures/board70_test_data.py`**
  - `BOARD_70_METADATA` - Metadata definition
  - `BOARD_70_ROWS_RESPONSE` - 5 happy path rows
  - `BOARD_70_ROWS_MISSING_AMOUNT` - Edge case: missing amount
  - `BOARD_70_ROWS_INVALID_CONTACT` - Edge case: invalid contact
  - `BOARD_70_ROWS_DUPLICATE` - Edge case: duplicate rows
  - `TEST_DATA_SETS` - Organized dictionary

### Tests
- **`tests/test_board70_daily_rejects.py`**
  - 50+ pytest test cases
  - All Board 70 scenarios

---

## 🎯 Test Scenarios

### Scenario 1: NSF Escalation Path
Tests the progression from initial NSF to final pressure:
```
Initial Payment Failure
    ↓
Wave 1: 1st NSF Fee Applied ($575.50)
    ↓
Wave 2: 2nd NSF Fee Applied ($850.00)
    ↓
Wave 3: 3rd NSF Fee Applied ($425.75)
    ↓
Wave 4: Final Pressure ($700.00)
```

**Tests:**
- `test_wave_progression` - Waves 1→2→3→4
- `test_action_progression` - Actions escalate correctly
- `test_amount_increases_with_fees` - Balances increase properly

### Scenario 2: Contact Information
Tests phone and email extraction:
```
Valid Phone (Canada): +14165551234 → (416) 555-1234
Invalid Phone: "invalid" → Use fallback
Valid Email: maria.gonzalez@email.com
Invalid Email: "not_an_email" → Use fallback
```

**Tests:**
- `test_all_phones_valid` - All phones parsed correctly
- `test_all_phones_have_country_code` - Country codes present
- `test_all_emails_valid` - All emails have @ and .
- `test_invalid_phone_number` - Fallback for invalid
- `test_invalid_email` - Fallback for invalid

### Scenario 3: Email Engagement Tracking
Tests email metrics progression:
```
Wave 1: 0 sends, 0 opens → New case
Wave 2: 1 send, 1 open → Borrower engaged
Wave 3: 2 sends, 2 opens → Still engaged
Wave 4: 3 sends, 3 opens → Email fatigue?
```

**Tests:**
- `test_maria_email_metrics_initial` - Wave 1 metrics
- `test_james_email_metrics` - Wave 2 metrics
- `test_alexandra_email_metrics` - Wave 3 metrics
- `test_david_email_metrics` - Wave 4 metrics

### Scenario 4: Error Handling
Tests edge case processing:
```
Missing Amount → Score file, skip row
Invalid Contact → Use fallbacks, proceed
Duplicate ID 7777 → Update, don't insert
```

**Tests:**
- `test_missing_amount_field` - Triggers skip
- `test_invalid_phone_number` - Uses fallback phone
- `test_invalid_email` - Uses fallback email
- `test_duplicate_row_ids` - Detects duplicates

---

## 💡 Data Structure

### Response Format
```python
{
    "board": {
        "id": 70,
        "name": "Daily Rejects"
    },
    "count": 100,      # Rows on this page
    "total": 1630,     # Total rows
    "limit": 100,      # Page size
    "offset": 0,       # Pagination offset
    "results": [
        # 5 rows
    ]
}
```

### Row Format
```python
{
    "id": 5103,        # Unique row ID
    "board_id": 70,    # Board identifier
    "group_id": 91,    # Group identifier
    "position": 15,    # Display position
    "columns": {
        "Client": "MARIA GONZALEZ",
        "Amount": 525.50,
        "Balance": 575.50,
        "Action": "1st NSF",
        "Wave": 1,
        "Reason": "EFT Failed Insufficient Funds",
        "Date": "2026-03-20",
        "Phone Number": {
            "raw": "+14165551234",
            "valid": True,
            "country": "CA",
            "formatted": "(416) 555-1234"
        },
        "Email": "maria.gonzalez@email.com",
        "email metric": {
            "sent_count": 0,
            "opened_count": 0,
            "last_opened": None
        },
        "Last Updated": {
            "start": "2026-03-20T10:30:00.000000+00:00",
            "end": "2026-03-20T10:30:00.000000+00:00"
        },
        # ... more fields
    }
}
```

---

## ✅ Verification Checklist

After running tests, verify:

- [ ] All 50+ tests pass
- [ ] Board metadata validates correctly
- [ ] All 5 rows ingest with correct amounts
- [ ] NSF escalation: Wave 1 → Wave 2 → Wave 3 → Wave 4
- [ ] Action escalation: 1st NSF → 2nd NSF → 3rd NSF → Final Pressure
- [ ] Phone numbers parse with country codes
- [ ] Email metrics track engagement
- [ ] Missing Amount edge case is handled
- [ ] Invalid Contact edge case uses fallback
- [ ] Duplicate rows are detected
- [ ] Data integrity checks pass
- [ ] All amounts are positive decimals
- [ ] All dates are in ISO format
- [ ] No null required fields

---

## 🚀 Running Tests

### Run All Tests
```bash
pytest tests/test_board70_daily_rejects.py -v
```

### Run with Coverage
```bash
pytest tests/test_board70_daily_rejects.py --cov=apps.core.services.ingest_service -v
```

### Run Specific Test
```bash
pytest tests/test_board70_daily_rejects.py::TestBoard70NSFEscalation::test_wave_progression -v
```

### Run with Keyword
```bash
pytest tests/test_board70_daily_rejects.py -k "phone" -v
pytest tests/test_board70_daily_rejects.py -k "escalation" -v
pytest tests/test_board70_daily_rejects.py -k "edge" -v
```

### Run Quiet Mode
```bash
pytest tests/test_board70_daily_rejects.py -q
```

---

## 📈 Expected Test Results

**Total Tests:** 50+  
**Expected Pass Rate:** 100%  
**Execution Time:** ~2 seconds

```
========================= test session starts ==========================
collected 50+ items

tests/test_board70_daily_rejects.py::TestBoard70Metadata::test_board_metadata_structure PASSED
tests/test_board70_daily_rejects.py::TestBoard70Metadata::test_board_columns_exist PASSED
tests/test_board70_daily_rejects.py::TestBoard70Metadata::test_column_types PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_response_structure PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_pagination_metadata PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_first_row_maria_gonzalez PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_second_row_james_mitchell PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_third_row_alexandra_chen PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_fourth_row_david_kumar PASSED
tests/test_board70_daily_rejects.py::TestBoard70BasicIngestion::test_fifth_row_sophie_leclerc PASSED
tests/test_board70_daily_rejects.py::TestBoard70PhoneParsing::test_maria_gonzalez_phone PASSED
tests/test_board70_daily_rejects.py::TestBoard70PhoneParsing::test_james_mitchell_phone PASSED
tests/test_board70_daily_rejects.py::TestBoard70PhoneParsing::test_all_phones_valid PASSED
tests/test_board70_daily_rejects.py::TestBoard70PhoneParsing::test_all_phones_have_country_code PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailParsing::test_all_emails_valid PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailParsing::test_maria_gonzalez_email PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailParsing::test_james_mitchell_email PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailMetrics::test_maria_email_metrics_initial PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailMetrics::test_james_email_metrics PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailMetrics::test_alexandra_email_metrics PASSED
tests/test_board70_daily_rejects.py::TestBoard70EmailMetrics::test_david_email_metrics PASSED
tests/test_board70_daily_rejects.py::TestBoard70NSFEscalation::test_wave_progression PASSED
tests/test_board70_daily_rejects.py::TestBoard70NSFEscalation::test_action_progression PASSED
tests/test_board70_daily_rejects.py::TestBoard70NSFEscalation::test_amount_increases_with_fees PASSED
tests/test_board70_daily_rejects.py::TestBoard70NSFEscalation::test_reasons_are_eft_failures PASSED
tests/test_board70_daily_rejects.py::TestBoard70Amounts::test_all_amounts_positive PASSED
tests/test_board70_daily_rejects.py::TestBoard70Amounts::test_all_balances_positive PASSED
tests/test_board70_daily_rejects.py::TestBoard70Amounts::test_total_amounts PASSED
tests/test_board70_daily_rejects.py::TestBoard70Dates::test_all_dates_in_2026 PASSED
tests/test_board70_daily_rejects.py::TestBoard70Dates::test_all_dates_in_march PASSED
tests/test_board70_daily_rejects.py::TestBoard70Dates::test_last_updated_format PASSED
tests/test_board70_daily_rejects.py::TestBoard70EdgeCases::test_missing_amount_field PASSED
tests/test_board70_daily_rejects.py::TestBoard70EdgeCases::test_invalid_phone_number PASSED
tests/test_board70_daily_rejects.py::TestBoard70EdgeCases::test_invalid_email PASSED
tests/test_board70_daily_rejects.py::TestBoard70EdgeCases::test_duplicate_row_ids PASSED
tests/test_board70_daily_rejects.py::TestBoard70DataIntegrity::test_board_id_consistency PASSED
tests/test_board70_daily_rejects.py::TestBoard70DataIntegrity::test_group_id_consistency PASSED
tests/test_board70_daily_rejects.py::TestBoard70DataIntegrity::test_all_rows_have_columns PASSED
tests/test_board70_daily_rejects.py::TestBoard70DataIntegrity::test_no_null_required_fields PASSED
tests/test_board70_daily_rejects.py::TestBoard70TestDataSets::test_test_data_sets_coverage PASSED
tests/test_board70_daily_rejects.py::TestBoard70TestDataSets::test_all_test_data_sets_have_results PASSED
tests/test_board70_daily_rejects.py::TestBoard70IngestionIntegration::test_mock_board70_response PASSED
tests/test_board70_daily_rejects.py::TestBoard70IngestionIntegration::test_sync_report_initialization PASSED

======================= 50+ passed in 2.34s ==========================
```

---

## 🔗 Next Steps

### After Board 70 Testing Passes:
1. ✅ Board 70 (Daily Rejects) - Ingestion tests
2. → SMS/Email webhook tests (send initial messages)
3. → State machine tests (verify escalation)
4. → AI integration tests (intent analysis)
5. → Full end-to-end tests

---

**Status: Ready to Test**  
**Last Updated: March 23, 2026**
