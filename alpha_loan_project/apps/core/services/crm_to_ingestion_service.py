"""Service to process CRMData and create IngestionData records."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Any

from django.db import transaction
from django.utils import timezone

from apps.collections.models import CRMData, IngestionData


_PHONE_DIGITS_RE = re.compile(r"\D")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


class CRMToIngestionService:
    """
    Reads from CRMData table, normalizes data, and saves to IngestionData table.
    
    Flow:
    1. Read raw CRM data from crm_data table
    2. Normalize: phone (E.164), reason codes, wave (1-4), amounts
    3. Save to ingestion_data table with link to crm_data
    """
    
    FEE_AMOUNT = Decimal("50.00")
    
    REASON_ALIASES = {
        "account frozen": "ACCOUNT_FROZEN",
        "account freezed": "ACCOUNT_FROZEN",
        "frozen account": "ACCOUNT_FROZEN",
        "eft failed frozen account": "EFT_FAILED_FROZEN_ACCOUNT",
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
        "payment stopped recalled": "PAYMENT_STOPPED_RECALLED",
        "eft failed no debit allowed": "EFT_FAILED_NO_DEBIT_ALLOWED",
        "eft failed refused no agreement": "EFT_FAILED_REFUSED_NO_AGREEMENT",
        "closed acc": "CLOSED_ACC",
        "closed account": "CLOSED_ACC",
        "eft failed insufficient funds": "NSF_EFT_INSUFFICIENT_FUNDS",
        "unknown reason": "UNKNOWN_REASON",
    }
    
    def process_all(self, *, limit: Optional[int] = None) -> Dict[str, Any]:
        """
        Process all CRMData records that don't have ingestion records yet.
        Returns processing stats.
        """
        queryset = CRMData.objects.all().order_by('-row_id')
        
        if limit:
            queryset = queryset[:limit]
        
        stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "error_samples": [],
        }
        
        for crm_record in queryset:
            stats["processed"] += 1
            try:
                result = self._process_crm_record(crm_record)
                if result == "created":
                    stats["created"] += 1
                elif result == "updated":
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                stats["errors"] += 1
                if len(stats["error_samples"]) < 10:
                    stats["error_samples"].append({
                        "row_id": crm_record.row_id,
                        "error": str(exc),
                    })
        
        return stats
    
    def process_by_row_ids(self, row_ids: List[int]) -> Dict[str, Any]:
        """Process specific CRM rows by their IDs."""
        stats = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "error_samples": [],
        }
        
        for row_id in row_ids:
            try:
                crm_record = CRMData.objects.get(row_id=row_id)
            except CRMData.DoesNotExist:
                stats["skipped"] += 1
                continue
            
            stats["processed"] += 1
            try:
                result = self._process_crm_record(crm_record)
                if result == "created":
                    stats["created"] += 1
                elif result == "updated":
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as exc:
                stats["errors"] += 1
                if len(stats["error_samples"]) < 10:
                    stats["error_samples"].append({
                        "row_id": row_id,
                        "error": str(exc),
                    })
        
        return stats
    
    def _process_crm_record(self, crm: CRMData) -> str:
        """
        Process a single CRMData record and create/update IngestionData.
        Returns: 'created', 'updated', or 'skipped'
        """
        validation_errors = []
        
        # Normalize phone
        phone = self._normalize_phone(crm.phone_number_raw)
        if not phone and crm.phone_number_raw:
            validation_errors.append("Invalid phone format")
        
        # Normalize email
        email = self._normalize_email(crm.email)
        if not email and crm.email:
            validation_errors.append("Invalid email format")
        
        # Normalize reason
        reason_code = self._normalize_reason(crm.reason or "")
        
        # Normalize wave (1-4)
        wave = self._normalize_wave(crm.wave)
        
        # Calculate amount + fee
        amount = crm.amount
        amount_plus_fee = None
        if amount is not None:
            amount_plus_fee = amount + self.FEE_AMOUNT
        else:
            validation_errors.append("Missing amount")
        
        # Borrower name
        borrower = crm.client or f"Borrower {crm.row_id}"
        
        # Determine validity
        is_valid = len(validation_errors) == 0 or (amount is not None and phone)
        
        with transaction.atomic():
            ingestion, created = IngestionData.objects.update_or_create(
                row_id=crm.row_id,
                defaults={
                    "crm_data": crm,
                    "borrower": borrower,
                    "phone": phone,
                    "email": email,
                    "amount": amount,
                    "amount_plus_fee": amount_plus_fee,
                    "balance": crm.balance,
                    "reason_code": reason_code,
                    "wave": wave,
                    "is_valid": is_valid,
                    "validation_errors": validation_errors if validation_errors else None,
                }
            )
        
        return "created" if created else "updated"
    
    def _normalize_phone(self, value: Optional[str]) -> Optional[str]:
        """Normalize phone to E.164 format (+1xxxxxxxxxx)."""
        if not value:
            return None
        
        digits = _PHONE_DIGITS_RE.sub("", str(value))
        if not digits:
            return None
        
        # Remove leading 1 for 11-digit numbers
        if len(digits) == 11 and digits.startswith("1"):
            digits = digits[1:]
        
        # Must be 10 digits for North American numbers
        if len(digits) != 10:
            return None
        
        return f"+1{digits}"
    
    def _normalize_email(self, value: Optional[str]) -> Optional[str]:
        """Normalize and validate email."""
        if not value:
            return None
        
        cleaned = str(value).strip().lower()
        if not cleaned:
            return None
        
        if not _EMAIL_RE.match(cleaned):
            return None
        
        return cleaned
    
    def _normalize_reason(self, value: str) -> str:
        """Normalize reason to standard code."""
        normalized = _NON_ALNUM_RE.sub(" ", (value or "").strip().lower()).strip()
        
        if not normalized:
            return "UNKNOWN_EMPTY"
        
        if normalized in self.REASON_ALIASES:
            return self.REASON_ALIASES[normalized]
        
        return f"REASON_{normalized.upper().replace(' ', '_')}"
    
    def _normalize_wave(self, value) -> int:
        """Normalize wave to 1-4 range."""
        if value is None:
            return 1
        
        try:
            wave_int = int(float(value))
        except (ValueError, TypeError):
            return 1
        
        # Treat wave 0 as 1, wave 20+ as 4
        if wave_int <= 0:
            return 1
        if wave_int > 4:
            return 4
        
        return wave_int
