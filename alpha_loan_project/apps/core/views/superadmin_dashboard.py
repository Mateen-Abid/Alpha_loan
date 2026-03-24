"""Superadmin-only operational dashboard and execution API."""

from __future__ import annotations

import json
import os
import re
from typing import Dict

from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.ai.message_generation.gemini_message_generator import GeminiMessageGenerator
from apps.core.integrations import ICollectorClient, ICollectorClientError
from apps.core.services.ingest_service import CRMIngestService


_KV_PATTERN = re.compile(r"([a-zA-Z0-9_]+)=([^;\n]+)")


def _extract_meta(notes: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for key, value in _KV_PATTERN.findall(notes or ""):
        meta[key] = value.strip()
    return meta


@user_passes_test(lambda u: u.is_active and u.is_superuser)
def superadmin_dashboard(request):
    """Render interactive superadmin dashboard."""
    return render(request, "admin/superadmin_dashboard.html")


def _normalize_row_for_preview(row: Dict[str, object], ingest: CRMIngestService) -> Dict[str, object]:
    columns = row.get("columns") or {}
    reason_raw = ingest._pick_column(columns, ["Reason", "Return Reason", "return_reason"]) or ""
    reason_code = ingest._normalize_reason(reason_raw)
    amount = ingest._parse_decimal(ingest._pick_column(columns, ["Amount", "failed_payment_amount"]))
    balance = ingest._parse_decimal(ingest._pick_column(columns, ["Balance", "balance"]))
    phone = ingest._normalize_phone(
        ingest._pick_column(columns, ["Phone Number", "Phone", "Borrower Phone", "phone"]) or ""
    )
    email = ingest._normalize_email(ingest._pick_column(columns, ["Email", "Borrower Email", "email"]) or "")
    borrower_name = ingest._pick_column(columns, ["Client", "Borrower", "Name", "Customer"]) or f"Borrower {row.get('id')}"
    wave_raw = ingest._pick_column(columns, ["Wave", "wave"]) or "1"
    try:
        wave = max(1, min(4, int(float(wave_raw))))
    except Exception:
        wave = 1

    immediate_due = None
    if amount is not None:
        immediate_due = amount + CRMIngestService.FEE_AMOUNT

    return {
        "row_id": row.get("id"),
        "borrower_name": borrower_name,
        "reason_raw": reason_raw,
        "reason_code": reason_code,
        "amount": f"{amount:.2f}" if amount is not None else None,
        "balance": f"{balance:.2f}" if balance is not None else None,
        "immediate_due_with_fee": f"{immediate_due:.2f}" if immediate_due is not None else None,
        "phone": phone,
        "email": email,
        "wave": wave,
    }


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def superadmin_dashboard_execute(request):
    """
    Execute production-preview pipeline:
    1) Pull latest CRM rows (board 70 / group 91)
    2) Apply ingestion mapping preview
    3) Generate Gemini message preview
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    board_id = str(body.get("board_id", 70))
    group_id = int(body.get("group_id", 91))
    limit = max(1, min(10, int(body.get("limit", 5))))

    client = ICollectorClient()
    ingest = CRMIngestService(client=client)

    try:
        rows_payload = client.get_rows(board_id=board_id, group_id=group_id, limit=limit, offset=0)
    except ICollectorClientError as exc:
        return JsonResponse({"status": "failed", "error": str(exc)}, status=502)

    rows = rows_payload.get("results") or []
    recent_rows = []
    ingestion_preview = []

    for row in rows[:limit]:
        columns = row.get("columns") or {}
        recent_rows.append(
            {
                "row_id": row.get("id"),
                "client": columns.get("Client"),
                "reason": columns.get("Reason"),
                "amount": columns.get("Amount"),
                "balance": columns.get("Balance"),
                "action": columns.get("Action"),
                "wave": columns.get("Wave"),
            }
        )
        ingestion_preview.append(_normalize_row_for_preview(row, ingest))

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_previews = []
    if gemini_key:
        try:
            generator = GeminiMessageGenerator(gemini_key)
            for item in ingestion_preview:
                if not item.get("amount"):
                    gemini_previews.append(
                        {
                            "row_id": item.get("row_id"),
                            "borrower_name": item.get("borrower_name"),
                            "status": "skipped",
                            "message": "Amount missing, preview skipped.",
                        }
                    )
                    continue
                msg = generator.generate_collection_message(
                    borrower_name=item.get("borrower_name") or "Client",
                    failed_amount=float(item["amount"]),
                    nsf_fee=50.00,
                    current_balance=float(item["balance"]) if item.get("balance") else 0.0,
                    reason=item.get("reason_raw") or "Payment failed",
                    wave=int(item.get("wave") or 1),
                    channel="sms",
                )
                gemini_previews.append(
                    {
                        "row_id": item.get("row_id"),
                        "borrower_name": item.get("borrower_name"),
                        "status": "success",
                        "message": msg,
                    }
                )
        except Exception as exc:  # pragma: no cover
            gemini_previews = [{"status": "failed", "message": f"Gemini preview failed: {exc}"}]
    else:
        gemini_previews = [{"status": "skipped", "message": "GEMINI_API_KEY not configured."}]

    return JsonResponse(
        {
            "status": "success",
            "meta": {"board_id": board_id, "group_id": group_id, "rows_count": len(rows[:limit])},
            "recent_rows": recent_rows,
            "ingestion_preview": ingestion_preview,
            "gemini_preview": gemini_previews,
        }
    )
