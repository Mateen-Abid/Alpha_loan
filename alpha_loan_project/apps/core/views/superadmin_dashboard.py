"""Superadmin-only operational dashboard and execution API."""

from __future__ import annotations

import json
import re
from decimal import Decimal, InvalidOperation
from typing import Dict

from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.ai.constants import build_gemini_collection_message_prompt
from apps.core.integrations import ICollectorClient, ICollectorClientError
from apps.core.services.ingest_service import CRMIngestService
from apps.core.services.crm_to_ingestion_service import CRMToIngestionService
from apps.collections.models import CRMData, IngestionData


_KV_PATTERN = re.compile(r"([a-zA-Z0-9_]+)=([^;\n]+)")
_PLACEHOLDER_PATTERN = re.compile(r"\[[^\]]+\]")
_CALL_US_PATTERN = re.compile(r"\bcall\s+us\b[^.!?]*[.!?]?", re.IGNORECASE)
_FORMAL_PHRASE_PATTERN = re.compile(r"\b(please remit|to resolve|current balance is)\b", re.IGNORECASE)


def _extract_meta(notes: str) -> Dict[str, str]:
    meta: Dict[str, str] = {}
    for key, value in _KV_PATTERN.findall(notes or ""):
        meta[key] = value.strip()
    return meta


def _parse_decimal_safe(value) -> Decimal | None:
    """Safely parse a value to Decimal."""
    if value is None:
        return None
    try:
        if isinstance(value, dict):
            value = value.get("raw") or value.get("value")
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _extract_phone_parts(phone_data) -> Dict[str, object]:
    """Extract phone parts from CRM phone field."""
    if phone_data is None:
        return {"raw": None, "formatted": None, "country": None, "valid": None}
    if isinstance(phone_data, dict):
        return {
            "raw": phone_data.get("raw"),
            "formatted": phone_data.get("formatted"),
            "country": phone_data.get("country"),
            "valid": phone_data.get("valid"),
        }
    return {"raw": str(phone_data), "formatted": None, "country": None, "valid": None}


def _save_crm_row_to_db(row: Dict[str, object], board_id: str, group_id: int) -> CRMData:
    """
    Save a single CRM row to the database.
    Updates existing row if row_id exists, otherwise creates new.
    """
    columns = row.get("columns") or {}
    row_id = int(row.get("id") or 0)
    
    phone_parts = _extract_phone_parts(columns.get("Phone Number"))
    
    defaults = {
        "board_id": int(board_id),
        "group_id": group_id,
        "group_name": row.get("group_name"),
        "client": columns.get("Client"),
        "phone_number_raw": phone_parts["raw"],
        "phone_number_formatted": phone_parts["formatted"],
        "phone_number_country": phone_parts["country"],
        "phone_number_valid": phone_parts["valid"],
        "email": columns.get("Email"),
        "amount": _parse_decimal_safe(columns.get("Amount")),
        "balance": _parse_decimal_safe(columns.get("Balance")),
        "reason": columns.get("Reason"),
        "action": columns.get("Action"),
        "wave": _parse_decimal_safe(columns.get("Wave")),
        "agent": columns.get("Agent"),
        "lang": columns.get("Lang"),
        "cell": columns.get("Cell"),
        "ref": columns.get("Ref"),
        "time_zone": columns.get("Time Zone"),
        "work": columns.get("Work"),
        "comment": columns.get("Comment"),
        "world_clock": str(columns.get("World Clock")) if columns.get("World Clock") else None,
        "raw_columns_json": columns,
        "synced_at": timezone.now(),
    }
    
    crm_data, created = CRMData.objects.update_or_create(
        row_id=row_id,
        defaults=defaults,
    )
    return crm_data


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


def _build_collection_prompt(item: Dict[str, object]) -> str:
    borrower_name = str(item.get("borrower_name") or "Client").strip()
    first_name = borrower_name.split()[0] if borrower_name else "Client"
    failed_amount = float(item.get("amount") or 0.0)
    current_balance = float(item.get("balance") or failed_amount)
    reason = str(item.get("reason_raw") or "Payment failed")
    wave = int(item.get("wave") or 1)

    base_prompt = build_gemini_collection_message_prompt(
        first_name=first_name,
        failed_amount=failed_amount,
        nsf_fee=float(CRMIngestService.FEE_AMOUNT),
        current_balance=current_balance,
        reason=reason,
        wave=wave,
        tone="collections_controlled",
    )
    return (
        f"{base_prompt}\n\n"
        "Preview-specific constraints:\n"
        f"- CRM reason: {item.get('reason_raw')}\n"
        f"- Missed amount: ${item.get('amount')}\n"
        f"- Immediate target (amount + fee): ${item.get('immediate_due_with_fee')}\n"
        f"- Balance context only: ${item.get('balance')}\n"
        "- Do NOT ask borrower to call us.\n"
        "- Do NOT use placeholders like [Phone Number] or [Company].\n"
        "- Ask for direct payment/reply action only.\n"
        "- Return only final SMS text."
    )


def _sanitize_preview_message(message: str) -> str:
    cleaned = (message or "").strip()
    cleaned = _PLACEHOLDER_PATTERN.sub("", cleaned)
    cleaned = _CALL_US_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    if not cleaned:
        return "Please reply to this message to confirm payment arrangement."
    return cleaned


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except Exception:
        return default


def _build_contract_fallback_message(item: Dict[str, object]) -> str:
    borrower_name = str(item.get("borrower_name") or "Client").strip()
    first_name = borrower_name.split()[0] if borrower_name else "Client"
    wave = int(_to_float(item.get("wave"), 1.0))
    immediate_due = _to_float(item.get("immediate_due_with_fee"), _to_float(item.get("amount"), 0.0))

    if wave <= 1:
        return (
            f"hey {first_name}, this is mike from ilowns. your payment bounced and total due is ${immediate_due:.2f}. "
            "are you taking care of this today, or should I lock this for tomorrow morning?"
        )
    if wave == 2:
        return (
            f"{first_name}, this is still open at ${immediate_due:.2f} and needs to be handled. "
            "are you clearing this tonight, or am I setting it for tomorrow morning?"
        )
    if wave == 3:
        return (
            f"{first_name}, this has been sitting and total due is ${immediate_due:.2f}. "
            "are you handling this now, or do I mark it for tomorrow morning?"
        )
    return (
        f"{first_name}, we're at ${immediate_due:.2f} and this cannot keep waiting. "
        "are you closing this today, or should I lock tomorrow morning as final timing?"
    )


def _is_contract_compliant(message: str, item: Dict[str, object]) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    if _FORMAL_PHRASE_PATTERN.search(text):
        return False
    if " or " not in text or "?" not in text:
        return False
    wave = int(_to_float(item.get("wave"), 1.0))
    if wave <= 1 and ("mike" not in text or "ilowns" not in text):
        return False
    return True


def _find_row_by_id(
    client: ICollectorClient,
    *,
    board_id: str,
    group_id: int,
    row_id: int,
    chunk_size: int = 100,
    max_pages: int = 50,
) -> Dict[str, object] | None:
    offset = 0
    scanned_pages = 0
    while scanned_pages < max_pages:
        payload = client.get_rows(board_id=board_id, group_id=group_id, limit=chunk_size, offset=offset)
        rows = payload.get("results") or []
        if not rows:
            return None
        for row in rows:
            if int(row.get("id") or 0) == row_id:
                return row
        offset += chunk_size
        scanned_pages += 1
        total = int(payload.get("count") or 0)
        if total and offset >= total:
            return None
    return None


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

    action = str(body.get("action", "all")).strip().lower()
    if action not in {"all", "crm", "ingestion", "gemini"}:
        return JsonResponse({"status": "failed", "error": f"Unsupported action '{action}'."}, status=400)

    board_id = str(body.get("board_id", 70))
    group_id = int(body.get("group_id", 91))
    limit = max(1, min(100, int(body.get("limit", 25))))
    page = max(1, int(body.get("page", 1)))
    offset = (page - 1) * limit
    row_id_filter_raw = body.get("row_id")
    row_id_filter = None
    if row_id_filter_raw not in (None, "", "null"):
        try:
            row_id_filter = int(row_id_filter_raw)
        except (TypeError, ValueError):
            return JsonResponse({"status": "failed", "error": "row_id must be numeric."}, status=400)
    temperature = float(body.get("temperature", 0.2))
    max_new_tokens = int(body.get("max_new_tokens", 220))

    recent_rows = []
    ingestion_preview = []
    ingestion_stats = {}
    saved_to_db = 0
    rows = []
    total_count = 0
    total_pages = 1
    has_prev = False
    has_next = False

    # INGESTION ACTION: Read ALL from CRMData table, process, save to IngestionData table
    if action == "ingestion":
        ingestion_service = CRMToIngestionService()
        
        # Process ALL CRM data (or filtered by row_id if specified)
        if row_id_filter is not None:
            ingestion_stats = ingestion_service.process_by_row_ids([row_id_filter])
        else:
            # Process ALL CRM records
            ingestion_stats = ingestion_service.process_all()
        
        # Query ingestion data for display (paginated)
        ingestion_queryset = IngestionData.objects.all().order_by('-row_id')
        
        if row_id_filter is not None:
            ingestion_queryset = ingestion_queryset.filter(row_id=row_id_filter)
        
        total_count = ingestion_queryset.count()
        total_pages = max(1, ((total_count - 1) // limit) + 1) if total_count else 1
        has_prev = page > 1
        has_next = (offset + limit) < total_count
        
        # Get paginated ingestion records for display
        ingestion_records = list(ingestion_queryset[offset:offset + limit])
        ingestion_preview = [
            {
                "row_id": rec.row_id,
                "borrower_name": rec.borrower,
                "phone": rec.phone,
                "email": rec.email,
                "amount": str(rec.amount) if rec.amount else None,
                "immediate_due_with_fee": str(rec.amount_plus_fee) if rec.amount_plus_fee else None,
                "balance": str(rec.balance) if rec.balance else None,
                "reason_code": rec.reason_code,
                "wave": rec.wave,
                "is_valid": rec.is_valid,
                "validation_errors": rec.validation_errors,
            }
            for rec in ingestion_records
        ]
    
    # CRM/GEMINI/ALL ACTIONS: Fetch from API
    else:
        client = ICollectorClient()
        ingest = CRMIngestService(client=client)

        if row_id_filter is not None:
            # Use direct row fetch API for specific row ID
            try:
                row_data = client.get_row(str(row_id_filter))
                # API returns the row directly, wrap it for consistency
                if row_data and row_data.get("id"):
                    rows = [row_data]
                    total_count = 1
                else:
                    rows = []
                    total_count = 0
            except ICollectorClientError as exc:
                # Fallback to pagination search if direct fetch fails
                try:
                    found = _find_row_by_id(
                        client,
                        board_id=board_id,
                        group_id=group_id,
                        row_id=row_id_filter,
                        chunk_size=min(limit, 100),
                    )
                    rows = [found] if found else []
                    total_count = 1 if found else 0
                except ICollectorClientError as exc2:
                    return JsonResponse({"status": "failed", "error": str(exc2)}, status=502)
            page = 1
            offset = 0
        else:
            try:
                rows_payload = client.get_rows(board_id=board_id, group_id=group_id, limit=limit, offset=offset)
            except ICollectorClientError as exc:
                return JsonResponse({"status": "failed", "error": str(exc)}, status=502)
            rows = rows_payload.get("results") or []
            total_count = int(rows_payload.get("total") or rows_payload.get("count") or len(rows))
            total_pages = max(1, ((total_count - 1) // limit) + 1) if total_count else 1
            has_prev = page > 1
            has_next = (offset + len(rows)) < total_count

        for row in rows:
            columns = row.get("columns") or {}
            if action in {"all", "crm"}:
                # Save to CRMData table
                try:
                    _save_crm_row_to_db(row, board_id, group_id)
                    saved_to_db += 1
                except Exception as exc:
                    pass  # Continue even if save fails
                
                recent_rows.append(
                    {
                        "row_id": row.get("id"),
                        "client": columns.get("Client"),
                        "reason": columns.get("Reason"),
                        "amount": columns.get("Amount"),
                        "balance": columns.get("Balance"),
                        "action": columns.get("Action"),
                        "wave": columns.get("Wave"),
                        "raw_columns": columns,
                    }
                )
            if action in {"all", "gemini"}:
                ingestion_preview.append(_normalize_row_for_preview(row, ingest))

    gemini_previews = []
    if action in {"all", "gemini"}:
        for item in ingestion_preview:
            if not item.get("amount"):
                gemini_previews.append(
                    {
                        "row_id": item.get("row_id"),
                        "borrower_name": item.get("borrower_name"),
                        "phone": item.get("phone"),
                        "email": item.get("email"),
                        "status": "skipped",
                        "message": "Amount missing, preview skipped.",
                    }
                )
                continue
            try:
                llm_result = client.generate_collection_llm(
                    prompt=_build_collection_prompt(item),
                    temperature=temperature,
                    max_new_tokens=max_new_tokens,
                    idempotency_key=f"dash-llm-{item.get('row_id')}",
                )
                raw_message = llm_result.get("answer") or llm_result.get("raw") or ""
                sanitized_message = _sanitize_preview_message(raw_message)
                compliant = _is_contract_compliant(sanitized_message, item)
                gemini_previews.append(
                    {
                        "row_id": item.get("row_id"),
                        "borrower_name": item.get("borrower_name"),
                        "phone": item.get("phone"),
                        "email": item.get("email"),
                        "status": "success",
                        "message": sanitized_message if compliant else _build_contract_fallback_message(item),
                        "model": llm_result.get("model"),
                        "idempotent_replay": bool(llm_result.get("idempotent_replay")),
                        "generation_source": "client_gateway_api",
                        "contract_enforced": not compliant,
                    }
                )
            except ICollectorClientError as exc:
                gemini_previews.append(
                    {
                        "row_id": item.get("row_id"),
                        "borrower_name": item.get("borrower_name"),
                        "phone": item.get("phone"),
                        "email": item.get("email"),
                        "status": "failed",
                        "message": str(exc),
                    }
                )

    return JsonResponse(
        {
            "status": "success",
            "action": action,
            "meta": {
                "board_id": board_id,
                "group_id": group_id,
                "rows_count": len(rows),
                "count": total_count,
                "page": page,
                "limit": limit,
                "offset": offset,
                "total_pages": total_pages,
                "has_prev": has_prev,
                "has_next": has_next,
                "row_id_filter": row_id_filter,
                "saved_to_db": saved_to_db,
                "ingestion_stats": ingestion_stats,
            },
            "recent_rows": recent_rows,
            "ingestion_preview": ingestion_preview,
            "gemini_preview": gemini_previews,
        }
    )


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def superadmin_dashboard_send_sms(request):
    """Send SMS for a preview row using partner gateway."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    row_id = body.get("row_id")
    phone = str(body.get("phone") or "").strip()
    message = str(body.get("message") or "").strip()

    if not row_id:
        return JsonResponse({"status": "failed", "error": "row_id is required."}, status=400)
    if not phone:
        return JsonResponse({"status": "failed", "error": "phone is required."}, status=400)
    if not message:
        return JsonResponse({"status": "failed", "error": "message is required."}, status=400)

    client = ICollectorClient()
    try:
        result = client.send_sms(row_id=str(row_id), phone=phone, message=message)
    except ICollectorClientError as exc:
        return JsonResponse({"status": "failed", "error": str(exc)}, status=502)

    return JsonResponse(
        {
            "status": "success",
            "row_id": row_id,
            "phone": phone,
            "gateway_result": result,
        }
    )


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def superadmin_dashboard_send_email(request):
    """Send email for a preview row using partner gateway."""
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    row_id = body.get("row_id")
    to_email = str(body.get("to_email") or body.get("email") or "").strip()
    subject = str(body.get("subject") or "Account Update").strip()
    message = str(body.get("message") or body.get("body") or "").strip()

    if not row_id:
        return JsonResponse({"status": "failed", "error": "row_id is required."}, status=400)
    if not to_email:
        return JsonResponse({"status": "failed", "error": "to_email is required."}, status=400)
    if not message:
        return JsonResponse({"status": "failed", "error": "message is required."}, status=400)

    client = ICollectorClient()
    try:
        result = client.send_email(row_id=str(row_id), to_email=to_email, subject=subject, body=message)
    except ICollectorClientError as exc:
        return JsonResponse({"status": "failed", "error": str(exc)}, status=502)

    return JsonResponse(
        {
            "status": "success",
            "row_id": row_id,
            "to_email": to_email,
            "subject": subject,
            "gateway_result": result,
        }
    )
