"""
Daily Rejects (Board 70) Test Data - Focused Testing

This file contains ONLY Board 70 (Daily Rejects) test data for focused ingestion testing.
All dummy data mirrors real iCollector Partner Gateway responses.

Test Scope:
  - Board 70: "Daily Rejects" - tracks daily EFT failures with NSF fees
  - 5 sample rows showing NSF escalation (Wave 1-4)
  - Edge cases: Missing amounts, invalid contacts, duplicates
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

# ============================================================================
# 1. BOARD 70 METADATA
# ============================================================================

BOARD_70_METADATA = {
    "id": 70,
    "name": "Daily Rejects",
    "description": "Track daily rejects with actions, time zones, and balances.",
    "groups": [
        {
            "id": 91,
            "title": "Daily rejects",
            "position": 0
        }
    ],
    "columns": [
        {"id": 241, "title": "Client", "type": "text", "position": 0},
        {"id": 242, "title": "Agent", "type": "person", "position": 1},
        {"id": 243, "title": "Lang", "type": "status", "position": 2},
        {"id": 244, "title": "Date", "type": "date", "position": 3},
        {"id": 245, "title": "Reason", "type": "long_text", "position": 4},
        {"id": 246, "title": "Amount", "type": "number", "position": 5},
        {"id": 247, "title": "Action", "type": "status", "position": 6},
        {"id": 248, "title": "Phone Number", "type": "phone", "position": 7},
        {"id": 249, "title": "Email", "type": "email", "position": 8},
        {"id": 250, "title": "Time Zone", "type": "status", "position": 9},
        {"id": 251, "title": "Cell", "type": "status", "position": 10},
        {"id": 252, "title": "Ref", "type": "status", "position": 11},
        {"id": 253, "title": "Work", "type": "status", "position": 12},
        {"id": 254, "title": "Wave", "type": "number", "position": 13},
        {"id": 255, "title": "Last Updated", "type": "timeline", "position": 14},
        {"id": 256, "title": "Comment", "type": "long_text", "position": 15},
        {"id": 257, "title": "Balance", "type": "number", "position": 16},
        {"id": 325, "title": "email metric", "type": "email_metric", "position": 17},
        {"id": 328, "title": "world clock", "type": "world_clock", "position": 18},
        {"id": 513, "title": "Group Name", "type": "text", "position": 19},
    ]
}

# ============================================================================
# 2. BOARD 70 BASIC ROWS (Happy Path - NSF Escalation)
# ============================================================================

BOARD_70_ROWS_RESPONSE = {
    "board": {"id": 70, "name": "Daily Rejects"},
    "count": 100,
    "total": 1630,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 5103,
            "board_id": 70,
            "group_id": 91,
            "position": 15,
            "columns": {
                "Client": "MARIA GONZALEZ",
                "Agent": [34],
                "Lang": "opt_1",
                "Date": "2026-03-20",
                "Reason": "EFT Failed Insufficient Funds",
                "Amount": 525.50,
                "Action": "1st NSF",
                "Phone Number": {
                    "raw": "+14165551234",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-1234"
                },
                "Email": "maria.gonzalez@email.com",
                "Time Zone": "opt_2",
                "Cell": "Spoke",
                "Ref": {},
                "Work": "Select",
                "Wave": 1,
                "Last Updated": {
                    "end": "2026-03-20T10:30:00.000000+00:00",
                    "start": "2026-03-20T10:30:00.000000+00:00"
                },
                "Comment": "Initial nsf fee applied",
                "Balance": 575.50,
                "email metric": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "world clock": {}
            }
        },
        {
            "id": 5104,
            "board_id": 70,
            "group_id": 91,
            "position": 16,
            "columns": {
                "Client": "JAMES MITCHELL",
                "Agent": [24],
                "Lang": "opt_1",
                "Date": "2026-03-19",
                "Reason": "EFT Failed Stop Payment",
                "Amount": 750.00,
                "Action": "2nd NSF",
                "Phone Number": {
                    "raw": "+16045559876",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(604) 555-9876"
                },
                "Email": "james.m.mitchell@email.com",
                "Time Zone": "opt_3",
                "Cell": "opt_0",
                "Ref": {},
                "Work": "Select",
                "Wave": 2,
                "Last Updated": {
                    "end": "2026-03-19T14:20:15.000000+00:00",
                    "start": "2026-03-19T14:20:15.000000+00:00"
                },
                "Comment": "Second nsf, customer contacted",
                "Balance": 850.00,
                "email metric": {
                    "sent_count": 1,
                    "last_opened": "2026-03-19T15:00:00.000000Z",
                    "opened_count": 1
                },
                "world clock": {}
            }
        },
        {
            "id": 5105,
            "board_id": 70,
            "group_id": 91,
            "position": 17,
            "columns": {
                "Client": "ALEXANDRA CHEN",
                "Agent": [12],
                "Lang": "opt_1",
                "Date": "2026-03-18",
                "Reason": "EFT Failed NSF Account",
                "Amount": 325.75,
                "Action": "3rd NSF",
                "Phone Number": {
                    "raw": "+17895554422",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(789) 555-4422"
                },
                "Email": "a.chen.2022@email.com",
                "Time Zone": "opt_1",
                "Cell": "Spoke",
                "Ref": {},
                "Work": "Select",
                "Wave": 3,
                "Last Updated": {
                    "end": "2026-03-18T09:15:45.000000+00:00",
                    "start": "2026-03-18T09:15:45.000000+00:00"
                },
                "Comment": "Third nsf, escalation pending",
                "Balance": 425.75,
                "email metric": {
                    "sent_count": 2,
                    "last_opened": "2026-03-17T18:30:00.000000Z",
                    "opened_count": 2
                },
                "world clock": {}
            }
        },
        {
            "id": 5106,
            "board_id": 70,
            "group_id": 91,
            "position": 18,
            "columns": {
                "Client": "DAVID KUMAR",
                "Agent": [34],
                "Lang": "opt_0",
                "Date": "2026-03-17",
                "Reason": "EFT Failed Account Closed",
                "Amount": 600.00,
                "Action": "Final Pressure",
                "Phone Number": {
                    "raw": "+14165558899",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-8899"
                },
                "Email": "david.kumar.ind@email.com",
                "Time Zone": "opt_2",
                "Cell": "Select",
                "Ref": {},
                "Work": "Select",
                "Wave": 4,
                "Last Updated": {
                    "end": "2026-03-17T16:45:30.000000+00:00",
                    "start": "2026-03-17T16:45:30.000000+00:00"
                },
                "Comment": "Final nsf, legal action under review",
                "Balance": 700.00,
                "email metric": {
                    "sent_count": 3,
                    "last_opened": "2026-03-16T11:22:00.000000Z",
                    "opened_count": 3
                },
                "world clock": {}
            }
        },
        {
            "id": 5107,
            "board_id": 70,
            "group_id": 91,
            "position": 19,
            "columns": {
                "Client": "SOPHIE LECLERC",
                "Agent": [24],
                "Lang": "opt_1",
                "Date": "2026-03-20",
                "Reason": "EFT Failed Insufficient Funds",
                "Amount": 450.25,
                "Action": "1st NSF",
                "Phone Number": {
                    "raw": "+14185552200",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(418) 555-2200"
                },
                "Email": "sophie.leclerc123@email.com",
                "Time Zone": "opt_3",
                "Cell": "Spoke",
                "Ref": {},
                "Work": "Select",
                "Wave": 1,
                "Last Updated": {
                    "end": "2026-03-20T12:00:00.000000+00:00",
                    "start": "2026-03-20T12:00:00.000000+00:00"
                },
                "Comment": "New nsf case, initial contact pending",
                "Balance": 500.25,
                "email metric": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "world clock": {}
            }
        }
    ]
}

# ============================================================================
# 3. EDGE CASES - BOARD 70 ONLY
# ============================================================================

# Rows with missing Amount (should be skipped)
BOARD_70_ROWS_MISSING_AMOUNT = {
    "board": {"id": 70, "name": "Daily Rejects"},
    "count": 1,
    "total": 1,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 9999,
            "board_id": 70,
            "group_id": 91,
            "position": 100,
            "columns": {
                "Client": "UNKNOWN CLIENT",
                "Agent": [34],
                "Lang": "opt_1",
                "Date": "2026-03-20",
                "Reason": "EFT Failed",
                "Amount": None,
                "Action": "Review",
                "Phone Number": {
                    "raw": "+14165551111",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-1111"
                },
                "Email": "unknown@email.com",
                "Time Zone": "opt_2",
                "Cell": "Select",
                "Ref": {},
                "Work": "Select",
                "Wave": 1,
                "Last Updated": {
                    "end": "2026-03-20T09:00:00.000000+00:00",
                    "start": "2026-03-20T09:00:00.000000+00:00"
                },
                "Comment": "Invalid row - no amount",
                "Balance": None,
                "email metric": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "world clock": {}
            }
        }
    ]
}

# Rows with invalid phone/email (fallback patterns)
BOARD_70_ROWS_INVALID_CONTACT = {
    "board": {"id": 70, "name": "Daily Rejects"},
    "count": 1,
    "total": 1,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 8888,
            "board_id": 70,
            "group_id": 91,
            "position": 99,
            "columns": {
                "Client": "NO CONTACT USER",
                "Agent": [24],
                "Lang": "opt_1",
                "Date": "2026-03-19",
                "Reason": "EFT Failed",
                "Amount": 99.99,
                "Action": "Review",
                "Phone Number": {"raw": "invalid", "valid": False},
                "Email": "not_an_email",
                "Time Zone": "opt_1",
                "Cell": "Select",
                "Ref": {},
                "Work": "Select",
                "Wave": 1,
                "Last Updated": {
                    "end": "2026-03-19T09:00:00.000000+00:00",
                    "start": "2026-03-19T09:00:00.000000+00:00"
                },
                "Comment": "Bad contact info",
                "Balance": 199.99,
                "email metric": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "world clock": {}
            }
        }
    ]
}

# Duplicate rows with same ID (for idempotency testing)
BOARD_70_ROWS_DUPLICATE = {
    "board": {"id": 70, "name": "Daily Rejects"},
    "count": 2,
    "total": 2,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 7777,
            "board_id": 70,
            "group_id": 91,
            "position": 50,
            "columns": {
                "Client": "DUPLICATE TEST USER",
                "Agent": [12],
                "Lang": "opt_1",
                "Date": "2026-03-20",
                "Reason": "EFT Failed Insufficient Funds",
                "Amount": 111.11,
                "Action": "1st NSF",
                "Phone Number": {
                    "raw": "+14165551111",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-1111"
                },
                "Email": "duplicate@email.com",
                "Time Zone": "opt_2",
                "Cell": "Spoke",
                "Ref": {},
                "Work": "Select",
                "Wave": 1,
                "Last Updated": {
                    "end": "2026-03-20T10:00:00.000000+00:00",
                    "start": "2026-03-20T10:00:00.000000+00:00"
                },
                "Comment": "This is row 7777 - version 1",
                "Balance": 211.11,
                "email metric": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "world clock": {}
            }
        },
        {
            "id": 7777,
            "board_id": 70,
            "group_id": 91,
            "position": 51,
            "columns": {
                "Client": "DUPLICATE TEST USER",
                "Agent": [12],
                "Lang": "opt_1",
                "Date": "2026-03-20",
                "Reason": "EFT Failed Insufficient Funds",
                "Amount": 111.11,
                "Action": "1st NSF",
                "Phone Number": {
                    "raw": "+14165551111",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-1111"
                },
                "Email": "duplicate@email.com",
                "Time Zone": "opt_2",
                "Cell": "Spoke",
                "Ref": {},
                "Work": "Select",
                "Wave": 1,
                "Last Updated": {
                    "end": "2026-03-20T10:05:00.000000+00:00",
                    "start": "2026-03-20T10:05:00.000000+00:00"
                },
                "Comment": "This is row 7777 - version 2 (duplicate)",
                "Balance": 211.11,
                "email metric": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "world clock": {}
            }
        }
    ]
}

# ============================================================================
# 4. TEST DATA SETS (Board 70 Only)
# ============================================================================

TEST_DATA_SETS = {
    # Happy path - NSF escalation
    "board70_happy_path": BOARD_70_ROWS_RESPONSE,
    
    # Edge cases
    "board70_edge_missing_amount": BOARD_70_ROWS_MISSING_AMOUNT,
    "board70_edge_invalid_contact": BOARD_70_ROWS_INVALID_CONTACT,
    "board70_edge_duplicate_rows": BOARD_70_ROWS_DUPLICATE,
}
