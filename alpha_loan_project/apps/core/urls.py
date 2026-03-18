"""Core URL configuration."""

from django.urls import path

from apps.core.views import partner_gateway_views

urlpatterns = [
    path("ping/", partner_gateway_views.partner_ping, name="partner_ping"),
    path("crm/boards/", partner_gateway_views.crm_boards, name="crm_boards"),
    path("crm/board/<str:board_id>/rows/", partner_gateway_views.crm_board_rows, name="crm_board_rows"),
]

