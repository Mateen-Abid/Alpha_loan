"""Row Lookup Dashboard - View specific row data from database."""

from __future__ import annotations

import json

from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db import DataError
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.collections.models import CRMData, IngestionData, MessagesOutbound
from apps.core.integrations import ICollectorClient, ICollectorClientError
from apps.ai.constants import build_gemini_collection_message_prompt, build_openai_email_prompt
from apps.core.services.ingest_service import CRMIngestService
from apps.core.services.crm_to_ingestion_service import CRMToIngestionService


def _truncate_text(value: object, max_length: int) -> str:
    if value is None:
        return ""
    return str(value).strip()[:max_length]


@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup(request):
    """Render the row lookup dashboard."""
    return render(request, "admin/row_lookup.html")


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_fetch_all_crm(request):
    """
    Fetch all CRM rows from the API (not database).
    Returns paginated rows directly from iCollector API.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        body = {}

    page = max(1, int(body.get("page", 1)))
    limit = min(100, max(1, int(body.get("limit", 100))))
    offset = (page - 1) * limit
    board_id = str(body.get("board_id", 70))
    group_id = int(body.get("group_id", 91))

    client = ICollectorClient()
    
    try:
        payload = client.get_rows(board_id=board_id, group_id=group_id, limit=limit, offset=offset)
    except ICollectorClientError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    rows = payload.get("results") or []
    total_count = int(payload.get("total") or payload.get("count") or len(rows))
    total_pages = max(1, ((total_count - 1) // limit) + 1) if total_count else 1

    # Transform rows for display
    display_rows = []
    for row in rows:
        columns = row.get("columns") or {}
        phone_data = columns.get("Phone Number")
        phone_raw = None
        if isinstance(phone_data, dict):
            phone_raw = phone_data.get("raw") or phone_data.get("formatted")
        elif phone_data:
            phone_raw = str(phone_data)

        display_rows.append({
            "row_id": row.get("id"),
            "client": columns.get("Client"),
            "phone_raw": phone_raw,
            "amount": columns.get("Amount"),
            "balance": columns.get("Balance"),
            "reason": columns.get("Reason"),
            "wave": columns.get("Wave"),
            "action": columns.get("Action"),
            "email": columns.get("Email"),
        })

    return JsonResponse({
        "status": "success",
        "rows": display_rows,
        "page": page,
        "limit": limit,
        "total_count": total_count,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
    })


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_api(request):
    """
    API endpoint to fetch row data from database.
    Returns CRM data and Ingestion data for a specific row_id.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    row_id = body.get("row_id")
    if not row_id:
        return JsonResponse({"error": "row_id is required"}, status=400)

    try:
        row_id = int(row_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "row_id must be a number"}, status=400)

    # Fetch CRM data
    crm_data = None
    try:
        crm = CRMData.objects.get(row_id=row_id)
        crm_data = {
            "id": crm.id,
            "row_id": crm.row_id,
            "board_id": crm.board_id,
            "group_id": crm.group_id,
            "group_name": crm.group_name,
            "client": crm.client,
            "phone_number_raw": crm.phone_number_raw,
            "phone_number_formatted": crm.phone_number_formatted,
            "phone_number_country": crm.phone_number_country,
            "phone_number_valid": crm.phone_number_valid,
            "email": crm.email,
            "amount": str(crm.amount) if crm.amount else None,
            "balance": str(crm.balance) if crm.balance else None,
            "reason": crm.reason,
            "action": crm.action,
            "wave": str(crm.wave) if crm.wave else None,
            "agent": crm.agent,
            "lang": crm.lang,
            "date": str(crm.date) if crm.date else None,
            "cell": crm.cell,
            "ref": crm.ref,
            "time_zone": crm.time_zone,
            "work": crm.work,
            "comment": crm.comment,
            "raw_columns_json": crm.raw_columns_json,
            "synced_at": crm.synced_at.isoformat() if crm.synced_at else None,
            "created_at": crm.created_at.isoformat() if crm.created_at else None,
            "updated_at": crm.updated_at.isoformat() if crm.updated_at else None,
        }
    except CRMData.DoesNotExist:
        pass

    # Fetch Ingestion data
    ingestion_data = None
    try:
        ing = IngestionData.objects.get(row_id=row_id)
        ingestion_data = {
            "id": ing.id,
            "row_id": ing.row_id,
            "borrower": ing.borrower,
            "phone": ing.phone,
            "email": ing.email,
            "amount": str(ing.amount) if ing.amount else None,
            "amount_plus_fee": str(ing.amount_plus_fee) if ing.amount_plus_fee else None,
            "balance": str(ing.balance) if ing.balance else None,
            "reason_code": ing.reason_code,
            "wave": ing.wave,
            "is_valid": ing.is_valid,
            "validation_errors": ing.validation_errors,
            "message_generated": ing.message_generated,
            "message_sent": ing.message_sent,
            "last_message_at": ing.last_message_at.isoformat() if ing.last_message_at else None,
            "created_at": ing.created_at.isoformat() if ing.created_at else None,
            "updated_at": ing.updated_at.isoformat() if ing.updated_at else None,
        }
    except IngestionData.DoesNotExist:
        pass

    return JsonResponse({
        "status": "success",
        "row_id": row_id,
        "crm_data": crm_data,
        "ingestion_data": ingestion_data,
    })


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_generate_message(request):
    """
    Generate an SMS collection message using the client's LLM API.
    Uses the prompt from constants.py (build_gemini_collection_message_prompt).
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    row_id = body.get("row_id")
    if not row_id:
        return JsonResponse({"error": "row_id is required"}, status=400)

    try:
        row_id = int(row_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "row_id must be a number"}, status=400)

    # Get data from database
    crm_data = None
    ingestion_data = None
    
    try:
        crm_data = CRMData.objects.get(row_id=row_id)
    except CRMData.DoesNotExist:
        pass

    try:
        ingestion_data = IngestionData.objects.get(row_id=row_id)
    except IngestionData.DoesNotExist:
        pass

    if not crm_data and not ingestion_data:
        return JsonResponse({"error": "No data found for this row_id"}, status=404)

    # Extract data for prompt
    borrower_name = ingestion_data.borrower if ingestion_data else (crm_data.client if crm_data else "Client")
    first_name = borrower_name.split()[0] if borrower_name else "Client"
    
    failed_amount = float(ingestion_data.amount or 0) if ingestion_data else float(crm_data.amount or 0)
    current_balance = float(ingestion_data.balance or failed_amount) if ingestion_data else float(crm_data.balance or failed_amount)
    reason = crm_data.reason if crm_data else "Payment failed"
    wave = ingestion_data.wave if ingestion_data else 1
    nsf_fee = float(CRMIngestService.FEE_AMOUNT)

    # Build the prompt using the function from constants.py
    prompt = build_gemini_collection_message_prompt(
        first_name=first_name,
        failed_amount=failed_amount,
        nsf_fee=nsf_fee,
        current_balance=current_balance,
        reason=reason or "Payment failed",
        wave=wave,
        tone="collections_controlled",
    )

    # Call the client's LLM API with the prompt from constants.py
    client = ICollectorClient()
    try:
        llm_result = client.generate_collection_llm(
            prompt=prompt,
            temperature=0.2,
            max_new_tokens=220,
            idempotency_key=f"row-lookup-{row_id}-{timezone.now().timestamp()}",
        )
        
        message = llm_result.get("answer") or llm_result.get("raw") or llm_result.get("text") or ""
        model = llm_result.get("model", "unknown")
        
        if not message:
            return JsonResponse({"error": "LLM API returned empty message"}, status=500)
        
        # Clean up the message
        message = message.strip()
        
        return JsonResponse({
            "status": "success",
            "row_id": row_id,
            "message": message,
            "model": model,
            "borrower": first_name,
            "amount": failed_amount,
            "total_due": failed_amount + nsf_fee,
            "wave": wave,
        })
        
    except ICollectorClientError as exc:
        return JsonResponse({"error": f"LLM API error: {str(exc)}"}, status=502)


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_generate_email_message(request):
    """
    Generate an email message body using the email prompt template from constants.py.
    Keeps email generation separated from SMS tone/prompt flow.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    row_id = body.get("row_id")
    if not row_id:
        return JsonResponse({"error": "row_id is required"}, status=400)

    try:
        row_id = int(row_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "row_id must be a number"}, status=400)

    crm_data = CRMData.objects.filter(row_id=row_id).first()
    ingestion_data = IngestionData.objects.filter(row_id=row_id).first()
    if not crm_data and not ingestion_data:
        return JsonResponse({"error": "No data found for this row_id"}, status=404)

    borrower_name = (
        (ingestion_data.borrower if ingestion_data and ingestion_data.borrower else None)
        or (crm_data.client if crm_data else None)
        or "Client"
    )
    tenant_name = str(getattr(settings, "ICOLLECTOR_TENANT", "") or "{{tenant}}").strip()
    deadline = str(getattr(settings, "COLLECTION_EMAIL_STOP_PAYMENT_DEADLINE", "") or "2pm EST today").strip()

    message = build_openai_email_prompt(
        {
            "borrower_name": borrower_name,
            "tenant": tenant_name,
            "stop_payment_deadline": deadline,
        }
    ).strip()

    return JsonResponse(
        {
            "status": "success",
            "row_id": row_id,
            "subject": "Account Update",
            "message": message,
            "generation_source": "constants_email_template",
        }
    )


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_send_sms(request):
    """
    Send SMS to a borrower and update message_sent status.
    Also saves the message to messages_outbound table.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    row_id = body.get("row_id")
    phone = _truncate_text(body.get("phone", ""), 50)
    message = body.get("message", "").strip()

    if not row_id:
        return JsonResponse({"error": "row_id is required"}, status=400)
    if not phone:
        return JsonResponse({"error": "phone is required"}, status=400)
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    try:
        row_id = int(row_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "row_id must be a number"}, status=400)

    # Get related data
    crm_data = None
    ingestion_data = None
    borrower_name = "Unknown"

    try:
        crm_data = CRMData.objects.get(row_id=row_id)
        borrower_name = crm_data.client or borrower_name
    except CRMData.DoesNotExist:
        pass

    try:
        ingestion_data = IngestionData.objects.get(row_id=row_id)
        if ingestion_data.borrower:
            borrower_name = ingestion_data.borrower
    except IngestionData.DoesNotExist:
        pass

    # Send SMS via iCollector API
    client = ICollectorClient()
    try:
        result = client.send_sms(row_id=str(row_id), phone=phone, message=message)
    except ICollectorClientError as exc:
        return JsonResponse({"error": f"SMS send failed: {str(exc)}"}, status=502)

    # Save to messages_outbound table
    sms_message_id = _truncate_text(
        result.get('sms_log', {}).get('message_id') if result else "",
        100,
    ) or None

    try:
        outbound = MessagesOutbound.objects.create(
            crm_data=crm_data,
            ingestion_data=ingestion_data,
            row_id=row_id,
            borrower_name=_truncate_text(borrower_name, 255),
            phone=phone,
            channel=MessagesOutbound.Channel.SMS,
            wave=ingestion_data.wave if ingestion_data else 1,
            amount=ingestion_data.amount if ingestion_data else None,
            total_due=ingestion_data.amount_plus_fee if ingestion_data else None,
            message_content=message,
            status=MessagesOutbound.Status.SENT,
            provider='icollector',
            provider_response=result,
            provider_message_id=sms_message_id,
            sent_at=timezone.now(),
        )
    except DataError:
        return JsonResponse(
            {
                "error": "SMS was sent but outbound logging failed due to field length limits. "
                         "Please shorten message metadata and retry."
            },
            status=500,
        )

    # Update ingestion_data message_sent to True
    if ingestion_data:
        ingestion_data.message_sent = True
        ingestion_data.message_generated = True
        ingestion_data.last_message_at = timezone.now()
        ingestion_data.save()

    return JsonResponse({
        "status": "success",
        "row_id": row_id,
        "phone": phone,
        "outbound_id": outbound.id,
        "message_sent": True,
        "api_response": result,
    })


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_send_email(request):
    """
    Send Email to a borrower and update message_sent status.
    Also saves the message to messages_outbound table.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    row_id = body.get("row_id")
    to_email = str(body.get("to_email", "") or "").strip()
    subject = str(body.get("subject", "") or "").strip() or "Account Update"
    message = str(body.get("message", "") or "").strip()

    if not row_id:
        return JsonResponse({"error": "row_id is required"}, status=400)
    if not to_email:
        return JsonResponse({"error": "to_email is required"}, status=400)
    if len(to_email) > 254:
        return JsonResponse({"error": "to_email exceeds max length (254)."}, status=400)
    if not message:
        return JsonResponse({"error": "message is required"}, status=400)

    try:
        row_id = int(row_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "row_id must be a number"}, status=400)

    # Get related data
    crm_data = None
    ingestion_data = None
    borrower_name = "Unknown"

    try:
        crm_data = CRMData.objects.get(row_id=row_id)
        borrower_name = crm_data.client or borrower_name
    except CRMData.DoesNotExist:
        pass

    try:
        ingestion_data = IngestionData.objects.get(row_id=row_id)
        if ingestion_data.borrower:
            borrower_name = ingestion_data.borrower
    except IngestionData.DoesNotExist:
        pass

    client = ICollectorClient()
    try:
        result = client.send_email(row_id=str(row_id), to_email=to_email, subject=subject, body=message)
    except ICollectorClientError as exc:
        return JsonResponse({"error": f"Email send failed: {str(exc)}"}, status=502)

    email_message_id = None
    if result:
        email_message_id = (
            result.get("email_log", {}).get("message_id")
            or result.get("message_id")
            or result.get("id")
        )
    email_message_id = _truncate_text(email_message_id, 100) or None

    try:
        outbound = MessagesOutbound.objects.create(
            crm_data=crm_data,
            ingestion_data=ingestion_data,
            row_id=row_id,
            borrower_name=_truncate_text(borrower_name, 255),
            email=to_email,
            channel=MessagesOutbound.Channel.EMAIL,
            wave=ingestion_data.wave if ingestion_data else 1,
            amount=ingestion_data.amount if ingestion_data else None,
            total_due=ingestion_data.amount_plus_fee if ingestion_data else None,
            message_content=message,
            status=MessagesOutbound.Status.SENT,
            provider='icollector',
            provider_response=result,
            provider_message_id=email_message_id,
            sent_at=timezone.now(),
        )
    except DataError:
        return JsonResponse(
            {
                "error": "Email was sent but outbound logging failed due to field length limits. "
                         "Please shorten message metadata and retry."
            },
            status=500,
        )

    if ingestion_data:
        ingestion_data.message_sent = True
        ingestion_data.message_generated = True
        ingestion_data.last_message_at = timezone.now()
        ingestion_data.save()

    return JsonResponse({
        "status": "success",
        "row_id": row_id,
        "to_email": to_email,
        "subject": subject,
        "outbound_id": outbound.id,
        "message_sent": True,
        "api_response": result,
    })


@require_POST
@user_passes_test(lambda u: u.is_active and u.is_superuser)
def row_lookup_run_ingestion(request):
    """
    Run CRM -> Ingestion mapping for a single row_id already in CRMData.
    """
    try:
        body = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    row_id = body.get("row_id")
    if not row_id:
        return JsonResponse({"error": "row_id is required"}, status=400)

    try:
        row_id = int(row_id)
    except (ValueError, TypeError):
        return JsonResponse({"error": "row_id must be a number"}, status=400)

    service = CRMToIngestionService()
    stats = service.process_by_row_ids([row_id])
    ingestion = IngestionData.objects.filter(row_id=row_id).first()

    return JsonResponse({
        "status": "success",
        "row_id": row_id,
        "ingestion_stats": stats,
        "ingestion_exists": bool(ingestion),
    })
