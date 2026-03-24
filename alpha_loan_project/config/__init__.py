"""Django/Celery configuration package."""

try:
    from config.celery import app as celery_app
except ModuleNotFoundError:
    # Allows Django management commands to run in environments
    # where Celery is not installed yet.
    celery_app = None

__all__ = ("celery_app",)
