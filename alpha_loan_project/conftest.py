"""Pytest configuration"""

import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test')
django.setup()

import pytest
from django.test import Client


@pytest.fixture
def client():
    """Django test client"""
    return Client()


@pytest.fixture
def db(db):
    """Database fixture"""
    return db
