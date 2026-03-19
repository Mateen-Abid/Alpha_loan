"""Partner gateway proxy views for Phase 1 data access."""

from __future__ import annotations

from typing import Optional

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.core.integrations import ICollectorClient, ICollectorClientError
from apps.core.services import CRMIngestService


def _parse_int_query_param(name: str, value: Optional[str]) -> tuple[Optional[int], Optional[str]]:
    if value in (None, ""):
        return None, None
    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, f"Invalid '{name}' query parameter: must be an integer."


@extend_schema(
    description="Proxy to iCollector Partner Gateway ping endpoint.",
    request=inline_serializer(name="PartnerPingRequest", fields={}),
    responses=inline_serializer(
        name="PartnerPingResponse",
        fields={"status": serializers.CharField(), "message": serializers.CharField(required=False), "error": serializers.CharField(required=False)},
    ),
)
@api_view(["POST"])
def partner_ping(request):
    """Proxy to POST /api/partner-gateway/v1/ping/."""
    try:
        result = ICollectorClient().ping()
        return Response(result, status=status.HTTP_200_OK)
    except ICollectorClientError as exc:
        return Response({"status": "failed", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@extend_schema(
    description="Fetch CRM boards from iCollector Partner Gateway.",
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
def crm_boards(request):
    """Proxy to GET /api/partner-gateway/v1/crm/boards/."""
    try:
        result = ICollectorClient().get_boards()
        return Response(result, status=status.HTTP_200_OK)
    except ICollectorClientError as exc:
        return Response({"status": "failed", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


@extend_schema(
    description="Fetch rows for a board from iCollector Partner Gateway.",
    parameters=[
        OpenApiParameter(name="limit", required=False, type=OpenApiTypes.INT, description="Maximum rows to fetch (default: 100)."),
        OpenApiParameter(name="offset", required=False, type=OpenApiTypes.INT, description="Pagination offset (default: 0)."),
        OpenApiParameter(name="group_id", required=False, type=OpenApiTypes.INT, description="Optional board group filter."),
    ],
    responses=OpenApiTypes.OBJECT,
)
@api_view(["GET"])
def crm_board_rows(request, board_id: str):
    """Proxy to GET /api/partner-gateway/v1/crm/board/{board_id}/rows/."""
    limit_raw = request.query_params.get("limit")
    offset_raw = request.query_params.get("offset")
    group_id_raw = request.query_params.get("group_id")

    limit, err = _parse_int_query_param("limit", limit_raw)
    if err:
        return Response({"status": "failed", "error": err}, status=status.HTTP_400_BAD_REQUEST)

    offset, err = _parse_int_query_param("offset", offset_raw)
    if err:
        return Response({"status": "failed", "error": err}, status=status.HTTP_400_BAD_REQUEST)

    group_id, err = _parse_int_query_param("group_id", group_id_raw)
    if err:
        return Response({"status": "failed", "error": err}, status=status.HTTP_400_BAD_REQUEST)

    if limit is None:
        limit = 100
    if offset is None:
        offset = 0
    if limit < 1 or limit > 500:
        return Response(
            {"status": "failed", "error": "Invalid 'limit': must be between 1 and 500."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if offset < 0:
        return Response(
            {"status": "failed", "error": "Invalid 'offset': must be >= 0."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        result = ICollectorClient().get_rows(
            board_id=board_id,
            limit=limit,
            offset=offset,
            group_id=group_id,
        )
        return Response(result, status=status.HTTP_200_OK)
    except ICollectorClientError as exc:
        return Response({"status": "failed", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)


class CRMIngestSyncRequestSerializer(serializers.Serializer):
    board_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=False,
        help_text="Board IDs to sync. Defaults to service defaults when omitted.",
    )
    group_ids_by_board = serializers.DictField(
        child=serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=False),
        required=False,
        help_text="Optional board -> group IDs mapping. Example: {'70': [91]}",
    )
    dry_run = serializers.BooleanField(required=False, default=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=500, default=100)
    max_pages_per_group = serializers.IntegerField(required=False, min_value=1, max_value=500, default=50)


@extend_schema(
    description=(
        "Run Step 2 CRM ingest pipeline (ingest + normalize + upsert + report). "
        "Use dry_run=true for safe validation before writing database records."
    ),
    request=CRMIngestSyncRequestSerializer,
    responses=OpenApiTypes.OBJECT,
)
@api_view(["POST"])
def crm_ingest_sync(request):
    serializer = CRMIngestSyncRequestSerializer(data=request.data or {})
    serializer.is_valid(raise_exception=True)
    payload = serializer.validated_data

    try:
        result = CRMIngestService().sync(
            board_ids=payload.get("board_ids"),
            group_ids_by_board=payload.get("group_ids_by_board"),
            dry_run=payload.get("dry_run", True),
            limit=payload.get("limit", 100),
            max_pages_per_group=payload.get("max_pages_per_group", 50),
        )
        return Response({"status": "success", "sync_report": result}, status=status.HTTP_200_OK)
    except ICollectorClientError as exc:
        return Response({"status": "failed", "error": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

