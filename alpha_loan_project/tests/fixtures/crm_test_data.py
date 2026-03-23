"""
Dummy CRM Test Data for Ingestion Testing

This file contains mock API responses that mirror the real iCollector Partner Gateway
responses. Use these fixtures to test the CRM ingestion pipeline without modifying
the actual ingestion code.

Boards:
  - Board 70: "Daily Rejects" - tracks daily EFT failures with NSF fees
  - Board 71: "E-Transfer" - tracks e-transfer seguips with due dates
  - Board 73: "E-Transfer Agreements" - manages e-transfer payment agreements
  - Board 74: "Received E-Transfer" - logs successfully received e-transfers
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

# ============================================================================
# 1. CRM BOARDS RESPONSE (GET /api/partner-gateway/v1/crm/boards/)
# ============================================================================

CRM_BOARDS_RESPONSE = {
    "results": [
        {
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
        },
        {
            "id": 71,
            "name": "E-Transfer",
            "description": "Follow up on e-transfer clients with actions, reminders, and comms.",
            "groups": [
                {"id": 93, "title": "Overdue", "position": 0},
                {"id": 94, "title": "Today", "position": 1},
                {"id": 95, "title": "Tomorrow", "position": 2},
                {"id": 96, "title": "Future", "position": 3},
            ],
            "columns": [
                {"id": 258, "title": "Client", "type": "text", "position": 0},
                {"id": 259, "title": "Agent", "type": "person", "position": 1},
                {"id": 260, "title": "Lang", "type": "status", "position": 2},
                {"id": 261, "title": "Due Date", "type": "date", "position": 3},
                {"id": 262, "title": "Next Due Date", "type": "date", "position": 4},
                {"id": 263, "title": "Amount", "type": "number", "position": 5},
                {"id": 264, "title": "Phone Number", "type": "phone", "position": 6},
                {"id": 265, "title": "Email", "type": "email", "position": 7},
                {"id": 266, "title": "Action", "type": "status", "position": 8},
                {"id": 267, "title": "Time Zone", "type": "status", "position": 9},
                {"id": 268, "title": "Frequency", "type": "status", "position": 10},
                {"id": 269, "title": "Last Updated", "type": "timeline", "position": 11},
                {"id": 270, "title": "Comment", "type": "long_text", "position": 12},
                {"id": 271, "title": "Balance", "type": "number", "position": 13},
                {"id": 272, "title": "Fees 1", "type": "checkbox", "position": 14},
                {"id": 273, "title": "Fees 2", "type": "checkbox", "position": 15},
                {"id": 326, "title": "email metrics", "type": "email_metric", "position": 16},
                {"id": 511, "title": "Group Name", "type": "text", "position": 17},
            ]
        },
        {
            "id": 73,
            "name": "E-Transfer Agreements",
            "description": "Manage e-transfer agreements with amounts and contact info.",
            "groups": [
                {"id": 98, "title": "Agreements", "position": 0}
            ],
            "columns": [
                {"id": 295, "title": "Client", "type": "text", "position": 0},
                {"id": 296, "title": "Agent", "type": "person", "position": 1},
                {"id": 297, "title": "Lang", "type": "status", "position": 2},
                {"id": 298, "title": "Date", "type": "date", "position": 3},
                {"id": 299, "title": "Amount", "type": "number", "position": 4},
                {"id": 300, "title": "Phone Number", "type": "phone", "position": 5},
                {"id": 301, "title": "Email", "type": "email", "position": 6},
                {"id": 302, "title": "Last Updated", "type": "timeline", "position": 7},
                {"id": 400, "title": "Group Name", "type": "text", "position": 9},
            ]
        },
        {
            "id": 74,
            "name": "Received E-Transfer",
            "description": "Log received e-transfers with acceptance and balances.",
            "groups": [
                {"id": 99, "title": "Received", "position": 0}
            ],
            "columns": [
                {"id": 305, "title": "Client", "type": "text", "position": 0},
                {"id": 306, "title": "Date", "type": "date", "position": 1},
                {"id": 307, "title": "Agent", "type": "person", "position": 2},
                {"id": 308, "title": "Email", "type": "email", "position": 3},
                {"id": 309, "title": "Amount", "type": "number", "position": 4},
                {"id": 310, "title": "Accepted", "type": "status", "position": 5},
                {"id": 311, "title": "Lang", "type": "status", "position": 6},
                {"id": 312, "title": "Last Updated", "type": "timeline", "position": 7},
                {"id": 313, "title": "Balance", "type": "number", "position": 8},
                {"id": 398, "title": "Group Name", "type": "text", "position": 9},
            ]
        }
    ]
}

# ============================================================================
# 2. BOARD 70 ROWS RESPONSE (Daily Rejects)
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
# 3. BOARD 71 ROWS RESPONSE (E-Transfer)
# ============================================================================

BOARD_71_ROWS_RESPONSE = {
    "board": {"id": 71, "name": "E-Transfer"},
    "count": 100,
    "total": 432,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 5200,
            "board_id": 71,
            "group_id": 93,
            "position": 0,
            "columns": {
                "Client": "ROBERT PATTERSON",
                "Agent": [12],
                "Lang": "opt_1",
                "Due Date": "2026-03-10",
                "Next Due Date": "2026-03-25",
                "Amount": 300.00,
                "Phone Number": {
                    "raw": "+16045552211",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(604) 555-2211"
                },
                "Email": "robert.patt@email.com",
                "Action": "Follow Up",
                "Time Zone": "opt_3",
                "Frequency": "Weekly",
                "Last Updated": {
                    "end": "2026-03-15T10:00:00.000000+00:00",
                    "start": "2026-03-15T10:00:00.000000+00:00"
                },
                "Comment": "Overdue etransfer, sent reminder",
                "Balance": 300.00,
                "Fees 1": False,
                "Fees 2": False,
                "email metrics": {
                    "sent_count": 1,
                    "last_opened": "2026-03-15T14:30:00.000000Z",
                    "opened_count": 1
                },
                "Group Name": "Overdue"
            }
        },
        {
            "id": 5201,
            "board_id": 71,
            "group_id": 94,
            "position": 1,
            "columns": {
                "Client": "JENNIFER TORRES",
                "Agent": [34],
                "Lang": "opt_0",
                "Due Date": "2026-03-20",
                "Next Due Date": "2026-03-20",
                "Amount": 500.00,
                "Phone Number": {
                    "raw": "+17785555050",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(778) 555-5050"
                },
                "Email": "j.torres.2024@email.com",
                "Action": "Send Today",
                "Time Zone": "opt_4",
                "Frequency": "Bi-weekly",
                "Last Updated": {
                    "end": "2026-03-20T08:30:00.000000+00:00",
                    "start": "2026-03-20T08:30:00.000000+00:00"
                },
                "Comment": "Due today, etransfer ready",
                "Balance": 500.00,
                "Fees 1": False,
                "Fees 2": False,
                "email metrics": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "Group Name": "Today"
            }
        },
        {
            "id": 5202,
            "board_id": 71,
            "group_id": 95,
            "position": 2,
            "columns": {
                "Client": "MICHAEL SOTO",
                "Agent": [24],
                "Lang": "opt_1",
                "Due Date": "2026-03-15",
                "Next Due Date": "2026-03-21",
                "Amount": 250.00,
                "Phone Number": {
                    "raw": "+14165557788",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-7788"
                },
                "Email": "michael.soto.m@email.com",
                "Action": "Send Tomorrow",
                "Time Zone": "opt_2",
                "Frequency": "Bi-weekly",
                "Last Updated": {
                    "end": "2026-03-20T11:15:00.000000+00:00",
                    "start": "2026-03-20T11:15:00.000000+00:00"
                },
                "Comment": "Scheduled for tomorrow",
                "Balance": 250.00,
                "Fees 1": False,
                "Fees 2": False,
                "email metrics": {
                    "sent_count": 1,
                    "last_opened": "2026-03-19T16:45:00.000000Z",
                    "opened_count": 0
                },
                "Group Name": "Tomorrow"
            }
        },
        {
            "id": 5203,
            "board_id": 71,
            "group_id": 96,
            "position": 3,
            "columns": {
                "Client": "PATRICK RYAN",
                "Agent": [12],
                "Lang": "opt_0",
                "Due Date": "2026-03-20",
                "Next Due Date": "2026-04-10",
                "Amount": 400.00,
                "Phone Number": {
                    "raw": "+19045559999",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(904) 555-9999"
                },
                "Email": "patrick.ryan.pm@email.com",
                "Action": "Schedule",
                "Time Zone": "opt_1",
                "Frequency": "Monthly",
                "Last Updated": {
                    "end": "2026-03-18T13:20:00.000000+00:00",
                    "start": "2026-03-18T13:20:00.000000+00:00"
                },
                "Comment": "Future etransfer scheduled for next month",
                "Balance": 400.00,
                "Fees 1": False,
                "Fees 2": False,
                "email metrics": {
                    "sent_count": 0,
                    "last_opened": None,
                    "opened_count": 0
                },
                "Group Name": "Future"
            }
        }
    ]
}

# ============================================================================
# 4. BOARD 73 ROWS RESPONSE (E-Transfer Agreements)
# ============================================================================

BOARD_73_ROWS_RESPONSE = {
    "board": {"id": 73, "name": "E-Transfer Agreements"},
    "count": 100,
    "total": 215,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 5300,
            "board_id": 73,
            "group_id": 98,
            "position": 0,
            "columns": {
                "Client": "LISA WANG",
                "Agent": [34],
                "Lang": "opt_1",
                "Date": "2026-03-01",
                "Amount": 150.00,
                "Phone Number": {
                    "raw": "+16045553344",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(604) 555-3344"
                },
                "Email": "lisa.wang.2023@email.com",
                "Last Updated": {
                    "end": "2026-03-15T09:30:00.000000+00:00",
                    "start": "2026-03-15T09:30:00.000000+00:00"
                },
                "Group Name": "Agreements"
            }
        },
        {
            "id": 5301,
            "board_id": 73,
            "group_id": 98,
            "position": 1,
            "columns": {
                "Client": "THOMAS BERNARD",
                "Agent": [24],
                "Lang": "opt_0",
                "Date": "2026-02-28",
                "Amount": 225.00,
                "Phone Number": {
                    "raw": "+14165554455",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(416) 555-4455"
                },
                "Email": "thomas.bernard.tb@email.com",
                "Last Updated": {
                    "end": "2026-03-10T14:45:00.000000+00:00",
                    "start": "2026-03-10T14:45:00.000000+00:00"
                },
                "Group Name": "Agreements"
            }
        },
        {
            "id": 5302,
            "board_id": 73,
            "group_id": 98,
            "position": 2,
            "columns": {
                "Client": "YASMIN PATEL",
                "Agent": [12],
                "Lang": "opt_1",
                "Date": "2026-03-05",
                "Amount": 175.50,
                "Phone Number": {
                    "raw": "+17785556666",
                    "valid": True,
                    "country": "CA",
                    "formatted": "(778) 555-6666"
                },
                "Email": "yasmin.patel.yp@email.com",
                "Last Updated": {
                    "end": "2026-03-12T11:00:00.000000+00:00",
                    "start": "2026-03-12T11:00:00.000000+00:00"
                },
                "Group Name": "Agreements"
            }
        }
    ]
}

# ============================================================================
# 5. BOARD 74 ROWS RESPONSE (Received E-Transfer)
# ============================================================================

BOARD_74_ROWS_RESPONSE = {
    "board": {"id": 74, "name": "Received E-Transfer"},
    "count": 100,
    "total": 89,
    "limit": 100,
    "offset": 0,
    "results": [
        {
            "id": 5400,
            "board_id": 74,
            "group_id": 99,
            "position": 0,
            "columns": {
                "Client": "RACHEL MORRISON",
                "Date": "2026-03-18",
                "Agent": [34],
                "Email": "rachel.morrison.rm@email.com",
                "Amount": 300.00,
                "Accepted": "opt_1",
                "Lang": "opt_1",
                "Last Updated": {
                    "end": "2026-03-18T16:20:00.000000+00:00",
                    "start": "2026-03-18T16:20:00.000000+00:00"
                },
                "Balance": 0.00,
                "Group Name": "Received"
            }
        },
        {
            "id": 5401,
            "board_id": 74,
            "group_id": 99,
            "position": 1,
            "columns": {
                "Client": "CHRISTOPHER ELLIS",
                "Date": "2026-03-17",
                "Agent": [24],
                "Email": "c.ellis.2024@email.com",
                "Amount": 500.00,
                "Accepted": "opt_1",
                "Lang": "opt_0",
                "Last Updated": {
                    "end": "2026-03-17T13:45:00.000000+00:00",
                    "start": "2026-03-17T13:45:00.000000+00:00"
                },
                "Balance": 0.00,
                "Group Name": "Received"
            }
        },
        {
            "id": 5402,
            "board_id": 74,
            "group_id": 99,
            "position": 2,
            "columns": {
                "Client": "NINA SANTOS",
                "Date": "2026-03-19",
                "Agent": [12],
                "Email": "nina.santos.ns@email.com",
                "Amount": 250.00,
                "Accepted": "opt_1",
                "Lang": "opt_1",
                "Last Updated": {
                    "end": "2026-03-19T10:15:00.000000+00:00",
                    "start": "2026-03-19T10:15:00.000000+00:00"
                },
                "Balance": 0.00,
                "Group Name": "Received"
            }
        }
    ]
}

# ============================================================================
# 6. EDGE CASES & ERROR SCENARIOS
# ============================================================================

# Rows with missing or invalid Amount (should be skipped during ingestion)
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
                "Amount": None,  # Missing Amount - should trigger MISSING_DUE_AMOUNT skip
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

# Rows with invalid phone/email (should use fallback patterns)
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
                "Phone Number": {"raw": "invalid", "valid": False},  # Invalid phone
                "Email": "not_an_email",  # Invalid email
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

# Duplicate rows with same row_id (for idempotency testing)
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
# 7. TEST DATA SETS (grouped for different test scenarios)
# ============================================================================

TEST_DATA_SETS = {
    # Basic happy path ingestion
    "basic_board70_ingestion": BOARD_70_ROWS_RESPONSE,
    
    # E-transfer follow-up scenarios
    "board71_etransfer_followup": BOARD_71_ROWS_RESPONSE,
    
    # Agreements tracking
    "board73_etransfer_agreements": BOARD_73_ROWS_RESPONSE,
    
    # Received payments
    "board74_received_etransfer": BOARD_74_ROWS_RESPONSE,
    
    # Edge cases
    "edge_case_missing_amount": BOARD_70_ROWS_MISSING_AMOUNT,
    "edge_case_invalid_contact": BOARD_70_ROWS_INVALID_CONTACT,
    "edge_case_duplicate_rows": BOARD_70_ROWS_DUPLICATE,
}
