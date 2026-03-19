"""CRM ingest service for Step 2 (ingest, normalize, upsert, report)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional

from django.db import transaction
from django.utils import timezone

from apps.collections.models import CollectionCase, TransactionLedger
from apps.core.integrations import ICollectorClient


_DECIMAL_RE = re.compile(r"-?\d+(?:\.\d+)?")
_PHONE_DIGITS_RE = re.compile(r"\D")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class SyncReport:
    """Aggregated sync report."""

    dry_run: bool
    processed: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    missing_due_amount_count: int = 0
    skipped_missing_due_amount_count: int = 0
    missing_phone_count: int = 0
    invalid_phone_count: int = 0
    missing_email_count: int = 0
    invalid_email_count: int = 0
    unknown_reason_counts: Dict[str, int] = field(default_factory=dict)
    reason_counts: Dict[str, int] = field(default_factory=dict)
    per_board_distribution: Dict[str, int] = field(default_factory=dict)
    per_group_distribution: Dict[str, int] = field(default_factory=dict)
    error_samples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "totals": {
                "processed": self.processed,
                "created": self.created,
                "updated": self.updated,
                "skipped": self.skipped,
                "errors": self.errors,
            },
            "unknown_reason_counts": self.unknown_reason_counts,
            "reason_counts": self.reason_counts,
            "missing_due_amount_count": self.missing_due_amount_count,
            "skipped_missing_due_amount_count": self.skipped_missing_due_amount_count,
            "contact_quality": {
                "missing_phone_count": self.missing_phone_count,
                "invalid_phone_count": self.invalid_phone_count,
                "rows_without_sms_usable_phone": self.missing_phone_count + self.invalid_phone_count,
                "missing_email_count": self.missing_email_count,
                "invalid_email_count": self.invalid_email_count,
            },
            "distribution": {
                "per_board": self.per_board_distribution,
                "per_group": self.per_group_distribution,
            },
            "error_samples": self.error_samples,
        }


class CRMIngestService:
    """
    Step 2 ingest service:
    - Ingest: paginated fetch from partner gateway
    - Normalize: reason, amounts, contacts, dates
    - Upsert: CollectionCase + idempotent TransactionLedger
    - Report: processing statistics and quality flags
    """

    FEE_AMOUNT = Decimal("50.00")
    DEFAULT_BOARD_IDS = ("70",)
    DEFAULT_GROUP_IDS_BY_BOARD = {"70": [91]}
    MAX_ERROR_SAMPLES = 25

    # Client-confirmed behavior: each reason should remain distinct.
    REASON_ALIASES = {
        "account frozen": "ACCOUNT_FROZEN",
        "account freezed": "ACCOUNT_FROZEN",
        "frozen account": "ACCOUNT_FROZEN",
        "nsf": "NSF",
        "1nsf": "NSF_1",
        "first nsf": "NSF_1",
        "first nsf on loan": "NSF_1",
        "2nsf": "NSF_2_CONSECUTIVE",
        "two consecutive nsf": "NSF_2_CONSECUTIVE",
        "3nsf": "NSF_3_CONSECUTIVE",
        "three consecutive nsf": "NSF_3_CONSECUTIVE",
        "1nsf first payment": "NSF_FIRST_PAYMENT",
        "first payment nsf": "NSF_FIRST_PAYMENT",
        "eft failed stop payment": "STOP_PMT",
        "stop_pmt": "STOP_PMT",
        "stop payment": "STOP_PMT",
        "closed acc": "CLOSED_ACC",
        "closed account": "CLOSED_ACC",
        "eft failed insufficient funds": "NSF_EFT_INSUFFICIENT_FUNDS",
    }
    NSF_LIKE_CODES = {
        "NSF",
        "NSF_1",
        "NSF_2_CONSECUTIVE",
        "NSF_3_CONSECUTIVE",
        "NSF_FIRST_PAYMENT",
        "NSF_EFT_INSUFFICIENT_FUNDS",
        "ACCOUNT_FROZEN",
    }

    def __init__(self, client: Optional[ICollectorClient] = None) -> None:
        self.client = client or ICollectorClient()

    def sync(
        self,
        *,
        board_ids: Optional[Iterable[int | str]] = None,
        group_ids_by_board: Optional[Dict[str, List[int]]] = None,
        dry_run: bool = True,
        limit: int = 100,
        max_pages_per_group: int = 50,
    ) -> Dict[str, Any]:
        report = SyncReport(dry_run=dry_run)

        selected_board_ids = [str(b) for b in (board_ids or self.DEFAULT_BOARD_IDS)]
        selected_groups = group_ids_by_board or self.DEFAULT_GROUP_IDS_BY_BOARD

        for board_id in selected_board_ids:
            groups = selected_groups.get(str(board_id), [None])
            if not groups:
                groups = [None]

            for group_id in groups:
                self._sync_group(
                    board_id=str(board_id),
                    group_id=group_id,
                    dry_run=dry_run,
                    limit=limit,
                    max_pages=max_pages_per_group,
                    report=report,
                )

        result = report.to_dict()
        result["config"] = {
            "board_ids": selected_board_ids,
            "group_ids_by_board": selected_groups,
            "limit": limit,
            "max_pages_per_group": max_pages_per_group,
            "fee_amount": f"{self.FEE_AMOUNT:.2f}",
        }
        return result

    def _sync_group(
        self,
        *,
        board_id: str,
        group_id: Optional[int],
        dry_run: bool,
        limit: int,
        max_pages: int,
        report: SyncReport,
    ) -> None:
        offset = 0
        for _ in range(max_pages):
            payload = self.client.get_rows(
                board_id=board_id,
                limit=limit,
                offset=offset,
                group_id=group_id,
            )
            rows = payload.get("results") or []
            if not rows:
                break

            for row in rows:
                report.processed += 1
                try:
                    self._process_row(row=row, board_id=board_id, group_id=group_id, dry_run=dry_run, report=report)
                except Exception as exc:  # pragma: no cover - defensive boundary
                    report.errors += 1
                    if len(report.error_samples) < self.MAX_ERROR_SAMPLES:
                        report.error_samples.append(
                            {
                                "board_id": board_id,
                                "group_id": group_id,
                                "row_id": row.get("id"),
                                "error": str(exc),
                            }
                        )

            if len(rows) < limit:
                break
            offset += limit

    def _process_row(
        self,
        *,
        row: Dict[str, Any],
        board_id: str,
        group_id: Optional[int],
        dry_run: bool,
        report: SyncReport,
    ) -> None:
        row_id = str(row.get("id", "")).strip()
        if not row_id:
            report.skipped += 1
            return

        columns = row.get("columns") or {}
        raw_reason = self._pick_column(columns, ["Reason", "Return Reason", "ReturnReason", "return_reason"]) or ""
        reason_code = self._normalize_reason(raw_reason)
        report.reason_counts[reason_code] = report.reason_counts.get(reason_code, 0) + 1
        if reason_code.startswith("UNKNOWN"):
            report.unknown_reason_counts[raw_reason or "<empty>"] = report.unknown_reason_counts.get(raw_reason or "<empty>", 0) + 1

        due_amount = self._parse_decimal(self._pick_column(columns, ["Amount", "Failed Payment Amount", "failed_payment_amount"]))
        balance_amount = self._parse_decimal(self._pick_column(columns, ["Balance", "Current Balance", "balance"]))
        if due_amount is None:
            # Client clarification: do not treat balance as missed-payment due.
            report.missing_due_amount_count += 1
            report.skipped += 1
            report.skipped_missing_due_amount_count += 1
            if len(report.error_samples) < self.MAX_ERROR_SAMPLES:
                report.error_samples.append(
                    {
                        "board_id": board_id,
                        "group_id": group_id,
                        "row_id": row_id,
                        "error": "Missing/invalid Amount; row skipped (Balance not used as due fallback).",
                    }
                )
            return

        immediate_due_with_fee = due_amount + self.FEE_AMOUNT

        borrower_phone_raw = self._pick_column(columns, ["Phone Number", "Phone", "Borrower Phone", "phone"]) or ""
        borrower_phone = self._normalize_phone(borrower_phone_raw)
        if not borrower_phone_raw:
            report.missing_phone_count += 1
        elif borrower_phone is None:
            report.invalid_phone_count += 1

        borrower_email_raw = self._pick_column(columns, ["Email", "Borrower Email", "email"]) or ""
        borrower_email = self._normalize_email(borrower_email_raw)
        if not borrower_email_raw:
            report.missing_email_count += 1
        elif borrower_email is None:
            report.invalid_email_count += 1

        borrower_name = self._pick_column(columns, ["Client", "Borrower", "Name", "Customer"]) or f"Borrower {row_id}"
        account_id = self._pick_column(columns, ["Account ID", "Account", "Loan ID", "account_id"]) or f"ROW-{row_id}"
        delinquent_date = self._parse_date(
            self._pick_column(columns, ["Date", "Failed Date", "Failed Payment Date", "Due Date"])
        ) or timezone.now().date()

        report.per_board_distribution[board_id] = report.per_board_distribution.get(board_id, 0) + 1
        group_key = f"{board_id}:{group_id if group_id is not None else row.get('group_id')}"
        report.per_group_distribution[group_key] = report.per_group_distribution.get(group_key, 0) + 1

        if dry_run:
            exists = CollectionCase.objects.filter(partner_row_id=row_id).exists()
            if exists:
                report.updated += 1
            else:
                report.created += 1
            return

        with transaction.atomic():
            collection_case, was_created = self._upsert_case(
                row_id=row_id,
                account_id=str(account_id),
                borrower_name=str(borrower_name),
                borrower_phone=borrower_phone or "",
                borrower_email=borrower_email,
                due_amount=due_amount,
                total_due=immediate_due_with_fee,
                delinquent_date=delinquent_date,
                reason_code=reason_code,
                raw_reason=raw_reason,
                board_id=board_id,
                group_id=group_id,
                balance_amount=balance_amount,
            )

            self._upsert_transactions(
                collection_case=collection_case,
                row_id=row_id,
                board_id=board_id,
                reason_code=reason_code,
                raw_reason=raw_reason,
                due_amount=due_amount,
                balance_amount=balance_amount,
                posted_date=delinquent_date,
            )

        if was_created:
            report.created += 1
        else:
            report.updated += 1

    def _upsert_case(
        self,
        *,
        row_id: str,
        account_id: str,
        borrower_name: str,
        borrower_phone: str,
        borrower_email: Optional[str],
        due_amount: Decimal,
        total_due: Decimal,
        delinquent_date: date,
        reason_code: str,
        raw_reason: str,
        board_id: str,
        group_id: Optional[int],
        balance_amount: Optional[Decimal],
    ) -> tuple[CollectionCase, bool]:
        collection_case = CollectionCase.objects.filter(partner_row_id=row_id).first()
        if collection_case is None:
            collection_case = CollectionCase.objects.filter(account_id=account_id).first()
            if collection_case and not collection_case.partner_row_id:
                collection_case.partner_row_id = row_id

        if collection_case is None:
            notes = (
                f"ingest_reason_code={reason_code}; "
                f"raw_reason={raw_reason}; "
                f"board_id={board_id}; "
                f"group_id={group_id}; "
                f"last_missed_due={due_amount:.2f}; "
                f"fee={self.FEE_AMOUNT:.2f}; "
                f"immediate_due_with_fee={total_due:.2f}; "
                f"balance_amount={(f'{balance_amount:.2f}' if balance_amount is not None else 'NA')}; "
                f"balance_plus_fee={(f'{(balance_amount + self.FEE_AMOUNT):.2f}' if balance_amount is not None else 'NA')}"
            )
            created_case = CollectionCase.objects.create(
                account_id=account_id,
                partner_row_id=row_id,
                borrower_name=borrower_name,
                borrower_email=borrower_email,
                borrower_phone=borrower_phone,
                principal_amount=due_amount,
                total_due=total_due,
                delinquent_date=delinquent_date,
                notes=notes,
            )
            return created_case, True

        if borrower_name:
            collection_case.borrower_name = borrower_name
        if borrower_phone:
            collection_case.borrower_phone = borrower_phone
        if borrower_email:
            collection_case.borrower_email = borrower_email
        collection_case.principal_amount = due_amount
        collection_case.total_due = total_due
        if delinquent_date:
            collection_case.delinquent_date = delinquent_date
        if not collection_case.partner_row_id:
            collection_case.partner_row_id = row_id
        collection_case.notes = self._append_note(
            existing=collection_case.notes,
            new_note=(
                f"ingest_reason_code={reason_code}; raw_reason={raw_reason}; board_id={board_id}; group_id={group_id}; "
                f"last_missed_due={due_amount:.2f}; fee={self.FEE_AMOUNT:.2f}; immediate_due_with_fee={total_due:.2f}; "
                f"balance_amount={(f'{balance_amount:.2f}' if balance_amount is not None else 'NA')}; "
                f"balance_plus_fee={(f'{(balance_amount + self.FEE_AMOUNT):.2f}' if balance_amount is not None else 'NA')}"
            ),
        )
        collection_case.save()
        return collection_case, False

    def _upsert_transactions(
        self,
        *,
        collection_case: CollectionCase,
        row_id: str,
        board_id: str,
        reason_code: str,
        raw_reason: str,
        due_amount: Decimal,
        balance_amount: Optional[Decimal],
        posted_date: date,
    ) -> None:
        event_signature = (
            f"ingest|board={board_id}|row={row_id}|date={posted_date.isoformat()}|reason={reason_code}|"
            f"due={due_amount:.2f}|balance={(balance_amount if balance_amount is not None else 'NA')}"
        )
        missed_ref = self._signature_ref(event_signature + "|missed")
        fee_ref = self._signature_ref(event_signature + "|fee")

        missed_type = (
            TransactionLedger.TransactionType.NSF
            if reason_code in self.NSF_LIKE_CODES
            else TransactionLedger.TransactionType.ADJUSTMENT
        )
        TransactionLedger.objects.get_or_create(
            collection_case=collection_case,
            external_reference=missed_ref,
            defaults={
                "transaction_type": missed_type,
                "amount": due_amount,
                "posted_date": posted_date,
                "created_by": "ingest_sync",
                "description": f"Missed payment ingest. reason_code={reason_code}; raw_reason={raw_reason}",
            },
        )
        TransactionLedger.objects.get_or_create(
            collection_case=collection_case,
            external_reference=fee_ref,
            defaults={
                "transaction_type": TransactionLedger.TransactionType.FEE,
                "amount": self.FEE_AMOUNT,
                "posted_date": posted_date,
                "created_by": "ingest_sync",
                "description": "Missed payment fee applied (+50).",
            },
        )

    @staticmethod
    def _signature_ref(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _append_note(*, existing: str, new_note: str) -> str:
        existing = (existing or "").strip()
        if not existing:
            return new_note
        if new_note in existing:
            return existing
        return f"{existing}\n{new_note}"

    @staticmethod
    def _pick_column(columns: Dict[str, Any], candidates: List[str]) -> Optional[str]:
        lower_map = {str(k).strip().lower(): v for k, v in columns.items()}
        for candidate in candidates:
            raw = lower_map.get(candidate.lower())
            if raw is None:
                continue
            if isinstance(raw, dict):
                if "label" in raw and raw.get("label") is not None:
                    return str(raw["label"]).strip()
                if "text" in raw and raw.get("text") is not None:
                    return str(raw["text"]).strip()
            if isinstance(raw, (list, tuple)):
                return ", ".join(str(item).strip() for item in raw if str(item).strip())
            return str(raw).strip()
        return None

    def _normalize_reason(self, value: str) -> str:
        normalized = _NON_ALNUM_RE.sub(" ", (value or "").strip().lower()).strip()
        if not normalized:
            return "UNKNOWN_EMPTY"
        if normalized in self.REASON_ALIASES:
            return self.REASON_ALIASES[normalized]
        return f"REASON_{normalized.upper().replace(' ', '_')}"

    @staticmethod
    def _parse_decimal(value: Optional[str]) -> Optional[Decimal]:
        if value is None:
            return None
        candidate = str(value).replace(",", "")
        match = _DECIMAL_RE.search(candidate)
        if not match:
            return None
        try:
            return Decimal(match.group(0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _normalize_phone(value: str) -> Optional[str]:
        digits = _PHONE_DIGITS_RE.sub("", value or "")
        if not digits:
            return None
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        if len(digits) != 10:
            return None
        return f"+1{digits}"

    @staticmethod
    def _normalize_email(value: str) -> Optional[str]:
        cleaned = (value or "").strip().lower()
        if not cleaned:
            return None
        if not _EMAIL_RE.match(cleaned):
            return None
        return cleaned

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        raw = value.strip()
        formats = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y")
        for fmt in formats:
            try:
                return datetime.strptime(raw, fmt).date()
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            return None


