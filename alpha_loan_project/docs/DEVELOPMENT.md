"""Development and Deployment Guide

## Quick Start

### 1. Local Development Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or on Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Database setup
python manage.py migrate
python manage.py createsuperuser

# Start all services
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Celery Beat
celery -A config beat -l info
```

### 2. Docker Setup
```bash
docker-compose up -d
# Access at http://localhost:8000
```

## Configuration

### Environment Variables
See `.env.example` for all required variables:
- Database credentials
- API keys (OpenAI, Heymarket, Telnyx, Gmail)
- Webhook secrets
- Redis URLs

### Settings Modules
- `config.settings.base` - Base settings (used by all)
- `config.settings.development` - Local development
- `config.settings.production` - Production
- `config.settings.test` - Testing

Use Django's `DJANGO_SETTINGS_MODULE` environment variable to switch.

## Architecture

### Apps

**collections**: Core collection management
- Models: CollectionCase, TransactionLedger, InteractionLedger, PaymentCommitment
- Workflows: Deterministic state machine for collections workflow
- Services: Business logic layer
- Repositories: Data access layer

**communications**: Multi-channel communication
- SMS: Heymarket integration
- Email: Gmail integration
- Voice: Telnyx/Twilio integration
- Router: Channel selection and routing

**ai**: AI processing
- Intent Detection: Classify borrower messages
- Message Generation: Generate responses
- Orchestrator: Coordinate AI operations

**webhooks**: Webhook handling
- Handlers: Process webhooks from external systems
- Validators: Signature and payload validation
- Processor: Route and process webhooks

**tasks**: Background jobs
- Follow-up: Scheduled follow-up messages
- Commitments: Payment commitment tracking
- Silence: Detect inactive cases

**core**: Shared utilities
- Constants: Shared constants
- Utils: Validators, decorators, encryption, logging
- Services: Cache, middleware
- Management: Custom Django commands

## Workflow Explanation

```
STEP_1
  ↓
STEP_2 (if borrower refuses)
  ↓
STEP_3 (if borrower refuses)
  ↓
STEP_4 (if borrower refuses)
  ↓
FINAL_PRESSURE (if borrower refuses)
```

Each step has:
- Specific communication strategy
- Escalation messages
- Duration in step
- Transition logic

## API Integration

### SMS (Heymarket)
- Send SMS: `SMSService.send_collection_sms()`
- Webhook: POST `/api/webhooks/sms/`
- Signature validation: HMAC-SHA256

### Email (Gmail)
- Send Email: `EmailService.send_collection_email()`
- Webhook: POST `/api/webhooks/email/`

### Voice (Telnyx/Twilio)
- Make Call: `VoiceService.make_collection_call()`
- Webhook: POST `/api/webhooks/voice/`
- Signature validation: Provider-specific

## Background Jobs

Scheduled via Celery Beat:
- **send_followup_messages**: Every 30 mins (business hours)
- **check_commitment_fulfillment**: Daily at midnight
- **send_commitment_reminder**: Daily at 8 AM
- **detect_silence_periods**: Every 6 hours

## Security

- API keys in environment variables only
- Webhook signatures validated
- Payload validation
- CORS configured
- HTTPS in production
- Sensitive data encrypted
- Rate limiting (can be added)

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov

# Specific test file
pytest apps/collections/tests/test_collections.py

# Specific test class
pytest apps/collections/tests/test_collections.py::CollectionCaseTests

# Specific test
pytest apps/collections/tests/test_collections.py::CollectionCaseTests::test_create_collection_case
```

## Deployment

### Prepare for Production
1. Set `DEBUG=False` in settings
2. Configure database (PostgreSQL)
3. Set up Redis
4. Configure all API keys and secrets
5. Set `ALLOWED_HOSTS`
6. Generate `SECRET_KEY` (use Django's secret key generator)
7. Configure HTTPS and SSL

### Deploy with Gunicorn
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### Docker Deployment
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Systemd Service (Linux)
Create `/etc/systemd/system/alpha-loan.service`:
```ini
[Unit]
Description=Alpha Loan Collections Platform
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/project
ExecStart=/path/to/venv/bin/gunicorn config.wsgi:application --bind unix:/tmp/alpha-loan.sock
Restart=always

[Install]
WantedBy=multi-user.target
```

## Monitoring & Logging

- Logs go to `/logs/alpha_loan.log`
- Configure centralized logging with ELK or similar
- Monitor Celery tasks via Flower
- Set up error tracking (Sentry)
- Monitor database performance

## Troubleshooting

### Celery not working
- Check Redis connection
- Verify `CELERY_BROKER_URL` in .env
- Check worker logs

### Webhooks not received
- Verify webhook URL is accessible
- Check firewall/network settings
- Validate signature secret matches provider config
- Check logs for errors

### Database errors
- Ensure migrations are run: `python manage.py migrate`
- Check database connection parameters
- Verify user has correct permissions

## Support & Documentation

See README.md for more information.
"""
