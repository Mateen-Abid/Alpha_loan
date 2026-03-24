"""Celery app configuration and beat schedules."""

from __future__ import annotations

import os

from celery import Celery
from celery.schedules import crontab


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")

app = Celery("alpha_loan_project")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


app.conf.beat_schedule = {
    "send-followup-messages": {
        "task": "apps.tasks.followup_tasks.send_followup_messages",
        "schedule": crontab(hour="8-20", minute="0"),
    },
    "check-commitment-fulfillment": {
        "task": "apps.tasks.promise_tasks.check_commitment_fulfillment",
        "schedule": crontab(hour="0", minute="0"),
    },
    "send-commitment-reminder": {
        "task": "apps.tasks.promise_tasks.send_commitment_reminder",
        "schedule": crontab(hour="8", minute="0"),
    },
    "detect-silence-periods": {
        "task": "apps.tasks.silence_detection_tasks.detect_silence_periods",
        "schedule": crontab(hour="*/6"),
    },
}

app.conf.timezone = "UTC"
