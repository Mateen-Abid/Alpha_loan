from decimal import Decimal

from django.test import TestCase

from apps.collections.models import CollectionCase, TransactionLedger
from apps.core.services.ingest_service import CRMIngestService


class _FakeClient:
    def __init__(self, rows):
        self._rows = rows

    def get_rows(self, board_id, limit=100, offset=0, group_id=None):
        batch = self._rows[offset : offset + limit]
        return {
            "board": {"id": int(board_id), "name": "Daily Rejects"},
            "count": len(batch),
            "total": len(self._rows),
            "results": batch,
        }


class CRMIngestServiceTests(TestCase):
    def test_dry_run_reports_expected_normalization(self):
        rows = [
            {
                "id": 12001,
                "board_id": 70,
                "group_id": 91,
                "columns": {
                    "Client": "John Doe",
                    "Reason": "Account freezed",
                    "Amount": "146.25",
                    "Balance": "196.25",
                    "Phone Number": "1 (514) 555-1212",
                    "Email": "John@example.com",
                },
            }
        ]
        service = CRMIngestService(client=_FakeClient(rows))

        report = service.sync(
            board_ids=[70],
            group_ids_by_board={"70": [91]},
            dry_run=True,
            limit=100,
            max_pages_per_group=1,
        )

        self.assertEqual(report["totals"]["processed"], 1)
        self.assertEqual(report["totals"]["created"], 1)
        self.assertEqual(report["totals"]["updated"], 0)
        self.assertEqual(report["reason_counts"]["ACCOUNT_FROZEN"], 1)
        self.assertEqual(report["missing_due_amount_count"], 0)
        self.assertEqual(report["skipped_missing_due_amount_count"], 0)
        self.assertEqual(report["contact_quality"]["rows_without_sms_usable_phone"], 0)

    def test_db_upsert_is_idempotent_for_same_row_signature(self):
        rows = [
            {
                "id": 12001,
                "board_id": 70,
                "group_id": 91,
                "columns": {
                    "Client": "John Doe",
                    "Reason": "NSF",
                    "Amount": "146.25",
                    "Balance": "196.25",
                    "Phone Number": "+1 514 555 1212",
                    "Email": "john@example.com",
                    "Date": "2026-03-19",
                },
            }
        ]
        service = CRMIngestService(client=_FakeClient(rows))

        first = service.sync(
            board_ids=[70],
            group_ids_by_board={"70": [91]},
            dry_run=False,
            limit=100,
            max_pages_per_group=1,
        )
        second = service.sync(
            board_ids=[70],
            group_ids_by_board={"70": [91]},
            dry_run=False,
            limit=100,
            max_pages_per_group=1,
        )

        self.assertEqual(first["totals"]["created"], 1)
        self.assertEqual(second["totals"]["updated"], 1)
        self.assertEqual(CollectionCase.objects.count(), 1)
        self.assertEqual(TransactionLedger.objects.count(), 2)

        case = CollectionCase.objects.get()
        self.assertEqual(case.partner_row_id, "12001")
        self.assertEqual(case.total_due, Decimal("196.25"))

    def test_missing_amount_is_skipped_and_not_fallback_to_balance(self):
        rows = [
            {
                "id": 12002,
                "board_id": 70,
                "group_id": 91,
                "columns": {
                    "Client": "Jane Doe",
                    "Reason": "Stop Payment",
                    "Amount": "",
                    "Balance": "650.00",
                    "Phone Number": "+1 514 555 9999",
                },
            }
        ]
        service = CRMIngestService(client=_FakeClient(rows))

        report = service.sync(
            board_ids=[70],
            group_ids_by_board={"70": [91]},
            dry_run=False,
            limit=100,
            max_pages_per_group=1,
        )

        self.assertEqual(report["totals"]["processed"], 1)
        self.assertEqual(report["totals"]["skipped"], 1)
        self.assertEqual(report["missing_due_amount_count"], 1)
        self.assertEqual(report["skipped_missing_due_amount_count"], 1)
        self.assertEqual(CollectionCase.objects.count(), 0)
        self.assertEqual(TransactionLedger.objects.count(), 0)
