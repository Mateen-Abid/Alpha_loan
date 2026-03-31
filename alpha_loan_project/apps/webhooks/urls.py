"""Webhooks URL Configuration"""

from django.urls import path
from .views import webhook_views
from apps.core.views.webhook_handler import icollector_webhook

urlpatterns = [
    path('sms/', webhook_views.sms_webhook, name='sms_webhook'),
    path('email/', webhook_views.email_webhook, name='email_webhook'),
    path('voice/', webhook_views.voice_webhook, name='voice_webhook'),
    path('crm/', webhook_views.crm_webhook, name='crm_webhook'),
    
    # iCollectorAI outbound webhook endpoint
    path('icollector/', icollector_webhook, name='icollector_webhook'),
]
