"""URL Configuration"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from apps.core.views.superadmin_dashboard import (
    superadmin_dashboard,
    superadmin_dashboard_execute,
    superadmin_dashboard_send_sms,
)
from apps.core.views.row_lookup import (
    row_lookup, 
    row_lookup_api, 
    row_lookup_fetch_all_crm,
    row_lookup_generate_message, 
    row_lookup_send_sms,
)

urlpatterns = [
    path('admin/superadmin-dashboard/', superadmin_dashboard, name='superadmin_dashboard'),
    path('admin/superadmin-dashboard/execute/', superadmin_dashboard_execute, name='superadmin_dashboard_execute'),
    path('admin/superadmin-dashboard/send-sms/', superadmin_dashboard_send_sms, name='superadmin_dashboard_send_sms'),
    path('admin/row-lookup/', row_lookup, name='row_lookup'),
    path('admin/row-lookup/api/', row_lookup_api, name='row_lookup_api'),
    path('admin/row-lookup/fetch-all-crm/', row_lookup_fetch_all_crm, name='row_lookup_fetch_all_crm'),
    path('admin/row-lookup/generate-message/', row_lookup_generate_message, name='row_lookup_generate_message'),
    path('admin/row-lookup/send-sms/', row_lookup_send_sms, name='row_lookup_send_sms'),
    path('admin/', admin.site.urls),
    
    # API Schema & Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
    # API Endpoints
    path('api/collections/', include('apps.collections.urls')),
    path('api/communications/', include('apps.communications.urls')),
    path('api/webhooks/', include('apps.webhooks.urls')),
    path('api/partner-gateway/v1/', include('apps.core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
