"""Celery Configuration - Task scheduling and configuration"""

from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('alpha_loan_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Celery Beat Schedule
app.conf.beat_schedule = {
    'send-followup-messages': {
        'task': 'apps.tasks.followup_tasks.send_followup_messages',
        'schedule': crontab(hour='9-17', minute='*/30'),  # Every 30 mins during business hours
    },
    'check-commitment-fulfillment': {
        'task': 'apps.tasks.promise_tasks.check_commitment_fulfillment',
        'schedule': crontab(hour='0', minute='0'),  # Daily at midnight
    },
    'send-commitment-reminder': {
        'task': 'apps.tasks.promise_tasks.send_commitment_reminder',
        'schedule': crontab(hour='8', minute='0'),  # Daily at 8 AM
    },
    'detect-silence-periods': {
        'task': 'apps.tasks.silence_detection_tasks.detect_silence_periods',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
}

app.conf.timezone = 'UTC'
