# Makefile for Development Tasks

.PHONY: help setup install migrate run celery beat test lint format clean docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make setup          - Set up virtual environment"
	@echo "  make install        - Install dependencies"
	@echo "  make migrate        - Run database migrations"
	@echo "  make run            - Run development server"
	@echo "  make celery         - Run Celery worker"
	@echo "  make beat           - Run Celery Beat scheduler"
	@echo "  make test           - Run tests with coverage"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code with black"
	@echo "  make clean          - Clean up generated files"
	@echo "  make docker-up      - Start Docker containers"
	@echo "  make docker-down    - Stop Docker containers"

setup:
	python -m venv venv
	@echo "Virtual environment created. Run: source venv/bin/activate"

install:
	pip install -r requirements.txt

migrate:
	python manage.py migrate

run:
	python manage.py runserver 0.0.0.0:8000

celery:
	celery -A config worker -l info

beat:
	celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

test:
	pytest --cov=apps --cov-report=html

lint:
	flake8 apps config
	isort --check-only apps config

format:
	black apps config
	isort apps config

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-migrate:
	docker-compose exec web python manage.py migrate
