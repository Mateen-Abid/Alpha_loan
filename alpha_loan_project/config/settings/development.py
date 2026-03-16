"""Development Settings - Local development configuration"""

from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

# Use SQLite for development if preferred
# DATABASES['default'] = {
#     'ENGINE': 'django.db.backends.sqlite3',
#     'NAME': BASE_DIR / 'db.sqlite3',
# }

# Development Celery settings (use eager mode for synchronous testing)
CELERY_TASK_ALWAYS_EAGER = False

CORS_ALLOW_ALL_ORIGINS = True

# Logging
LOGGING['loggers'] = {
    'django': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
}
