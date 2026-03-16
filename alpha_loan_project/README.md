# Alpha Loan Collections Automation Platform

Production-ready Django project for AI-powered loan collections automation using SMS, Email, and Voice communication.

## Features

- **Multi-Channel Communication**: SMS (Heymarket), Email (Gmail), Voice (Telnyx/Twilio)
- **Workflow Automation**: Deterministic state machine for collection workflow
- **AI Integration**: OpenAI for intent detection and message generation
- **Webhook Processing**: Secure webhook handling for all communication channels
- **Background Jobs**: Celery + Redis for async tasks and scheduling
- **Payment Tracking**: Transaction ledger and payment commitment tracking
- **Interaction Logging**: Complete audit trail of all communications

## Project Structure

```
alpha_loan_project/
├── config/                          # Django configuration
│   ├── settings/
│   │   ├── base.py                 # Base settings
│   │   ├── development.py          # Dev settings
│   │   ├── production.py           # Production settings
│   │   └── test.py                 # Test settings
│   ├── urls.py
│   └── wsgi.py
│
├── apps/
│   ├── collections/                # Core collection management
│   │   ├── models/
│   │   │   ├── collection_case.py
│   │   │   ├── transaction_ledger.py
│   │   │   ├── interaction_ledger.py
│   │   │   └── payment_commitment.py
│   │   ├── workflows/              # State machine
│   │   │   ├── state_machine.py
│   │   │   └── workflow_states.py
│   │   ├── services/               # Business logic
│   │   │   └── collection_service.py
│   │   ├── repositories/           # Data access
│   │   │   └── collection_case_repo.py
│   │   ├── views/
│   │   ├── admin/
│   │   └── tests/
│   │
│   ├── communications/             # Multi-channel communications
│   │   ├── sms/
│   │   │   ├── heymarket_client.py
│   │   │   └── sms_service.py
│   │   ├── email/
│   │   │   ├── gmail_client.py
│   │   │   └── email_service.py
│   │   ├── voice/
│   │   │   ├── telnyx_client.py
│   │   │   ├── twilio_client.py
│   │   │   └── voice_service.py
│   │   ├── services/
│   │   │   ├── communication_router.py
│   │   │   └── template_service.py
│   │   ├── views/
│   │   ├── admin/
│   │   └── tests/
│   │
│   ├── ai/                         # AI integration
│   │   ├── clients/
│   │   │   └── openai_client.py
│   │   ├── intent_detection/
│   │   │   ├── intent_analyzer.py
│   │   │   └── intent_types.py
│   │   ├── message_generation/
│   │   │   ├── message_generator.py
│   │   │   └── prompt_templates.py
│   │   ├── services/
│   │   │   └── ai_orchestrator.py
│   │   ├── views/
│   │   ├── admin/
│   │   └── tests/
│   │
│   ├── webhooks/                   # Webhook handling
│   │   ├── handlers/
│   │   │   ├── crm_webhook_handler.py
│   │   │   ├── sms_webhook_handler.py
│   │   │   ├── email_webhook_handler.py
│   │   │   └── voice_webhook_handler.py
│   │   ├── validators/
│   │   │   ├── signature_validator.py
│   │   │   └── payload_validator.py
│   │   ├── services/
│   │   │   └── webhook_processor.py
│   │   ├── views/
│   │   ├── admin/
│   │   └── tests/
│   │
│   ├── tasks/                      # Background jobs
│   │   ├── followup_tasks.py
│   │   ├── promise_tasks.py
│   │   ├── silence_detection_tasks.py
│   │   └── config.py              # Celery configuration
│   │
│   └── core/                       # Shared utilities
│       ├── constants/
│       │   └── __init__.py
│       ├── utils/
│       │   ├── validators.py
│       │   ├── decorators.py
│       │   ├── encryption.py
│       │   └── logging.py
│       ├── services/
│       │   └── cache_service.py
│       ├── middleware/
│       │   └── request_logging.py
│       └── management/
│           └── commands/
│
├── tests/                          # Test suite
│   ├── fixtures/
│   └── factories/
│
├── docs/                           # Documentation
├── static/                         # Static files
├── media/                          # User uploads
├── logs/                           # Log files
│
├── manage.py                       # Django management
├── requirements.txt                # Dependencies
├── .env.example                    # Environment template
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── conftest.py                     # Pytest config
└── pytest.ini
```

## Installation

### Prerequisites
- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- Docker & Docker Compose (optional)

### Local Setup

1. **Clone and setup**
```bash
cd alpha_loan_project
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your API keys and configuration
```

3. **Setup database**
```bash
python manage.py migrate
python manage.py createsuperuser
```

4. **Start services**
```bash
# In separate terminals:
# Terminal 1: Django
python manage.py runserver

# Terminal 2: Celery Worker
celery -A config worker -l info

# Terminal 3: Celery Beat (Scheduler)
celery -A config beat -l info
```

### Docker Setup

```bash
docker-compose up -d
```

Access the application at `http://localhost:8000`

## Workflow Explanation

The system implements a strict collections workflow:

1. **STEP_1 - Immediate Payment**: Initial contact requesting immediate payment
2. **STEP_2 - Double Payment**: Follow-up requesting 2x payment to catch up
3. **STEP_3 - Add NSF**: Inform of NSF fees that will be added
4. **STEP_4 - Split NSF**: Offer split payment arrangements
5. **FINAL_PRESSURE**: Final notice before legal action

Each step advances only when the borrower refuses to pay.

## API Integration

### SMS (Heymarket)
- Incoming SMS triggers webhook → Handler processes → AI analyzes intent
- Outbound SMS via `SMSService.send_collection_sms()`

### Email (Gmail)
- Incoming emails processed via webhook
- Outbound emails via `EmailService.send_collection_email()`

### Voice (Telnyx/Twilio)
- Outbound calls via `VoiceService.make_collection_call()`
- Call transcripts processed asynchronously  
- Intent detection triggers workflow transitions

## Background Jobs

Scheduled via Celery Beat:
- **send_followup_messages**: Every 30 mins during business hours
- **check_commitment_fulfillment**: Daily at midnight
- **send_commitment_reminder**: Daily at 8 AM
- **detect_silence_periods**: Every 6 hours

## Security

- API keys stored in environment variables
- Webhook signatures validated (HMAC-SHA256)
- Payload content validated
- Encrypted sensitive data
- CORS protected endpoints
- Rate limiting (can be added)

## Testing

```bash
pytest                          # Run all tests
pytest --cov                    # With coverage
pytest -v                       # Verbose output
```

## Deployment

See production settings in `config/settings/production.py`

1. Set environment variables
2. Run migrations: `python manage.py migrate`
3. Collect statics: `python manage.py collectstatic`
4. Start with gunicorn: `gunicorn config.wsgi:application`

## Development Guidelines

- Use Django ORM for database operations
- Service layer for business logic
- Repository pattern for data access
- Async tasks for long-running operations
- Webhook handlers don't perform heavy processing
- AI should only analyze/generate, not control workflow logic

## Support

For issues or questions, refer to the documentation in `docs/` or contact the development team.
