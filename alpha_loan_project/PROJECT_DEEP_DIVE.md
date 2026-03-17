# iCollector (Alpha Loan) Project Deep Dive

This document explains the current codebase in depth: what exists, how data flows, where each module is responsible, and what is still incomplete for full production behavior.

## 1) Project Purpose

`alpha_loan_project` is a Django-based collections automation platform for delinquent loan recovery.  
It combines deterministic workflow logic with AI-assisted borrower intent analysis and multi-channel communication (SMS, email, voice).

Primary business objective:
- Track delinquent accounts as `CollectionCase` records.
- Contact borrowers through channel services.
- Process borrower replies through webhooks.
- Analyze replies with AI.
- Update workflow state and schedule the next follow-up.

## 2) High-Level Architecture

Top-level folders:
- `config/`: Django settings, app URL mounting, ASGI/WSGI runtime.
- `apps/`: Domain apps (`collections`, `communications`, `ai`, `webhooks`, `tasks`, `core`).
- `docs/`: Existing architecture and development documents.
- Root runtime files: `manage.py`, `requirements.txt`, `.env.example`, `Dockerfile`, `docker-compose.yml`, `pytest.ini`.

Domain layering currently follows:
1. **Ingress**: webhooks receive external events.
2. **Orchestration**: webhook processor routes to handlers.
3. **Async processing**: Celery tasks run AI/state operations.
4. **Business domain**: collections service + workflow state machine.
5. **Egress**: communication router dispatches via SMS/email/voice clients.
6. **Persistence**: Django ORM to PostgreSQL models.

## 3) Technology Stack

From `requirements.txt` and settings:
- **Backend**: Django 4.2 + Django REST Framework.
- **Database**: PostgreSQL (`config/settings/base.py`).
- **Queue/Scheduler**: Celery + Redis + `django-celery-beat` + `django-celery-results`.
- **AI**: OpenAI Python SDK (`openai==0.27.6`).
- **Comms providers**: Twilio, custom Heymarket client, Gmail client scaffolding.
- **Cross-cutting**: CORS, caching (`django-redis`), encryption (`cryptography`), Sentry SDK.
- **Testing/quality**: pytest, pytest-django, pytest-cov, black, flake8, isort.

## 4) Runtime & Configuration

Entrypoints:
- `manage.py`: Django CLI entrypoint.
- `config/asgi.py` and `config/wsgi.py`: server runtime entrypoints.
- Root URL graph in `config/urls.py`.

Settings:
- `config/settings/base.py`: shared defaults (installed apps, middleware, DB, Celery, cache, logging, DRF).
- `config/settings/development.py`, `production.py`, `test.py`: env-specific overrides.

Environment:
- `.env.example` defines required operational secrets and URLs.

Important runtime note:
- Celery app is defined in `apps/tasks/config.py`.
- Some scripts reference `celery -A config ...`; verify Celery app exposure aligns with deployment entrypoint.

## 5) App-by-App Breakdown

### 5.1 `apps/collections` (Core debt collection domain)

Main responsibility: case lifecycle and financial/interaction records.

Key models:
- `CollectionCase` (`models/collection_case.py`): account + borrower + workflow/status + balances + follow-up schedule.
- `TransactionLedger` (`models/transaction_ledger.py`): monetary events (payments, fees, reversals, etc.).
- `InteractionLedger` (`models/interaction_ledger.py`): inbound/outbound communication audit trail and AI fields.
- `PaymentCommitment` (`models/payment_commitment.py`): promise-to-pay objects and fulfillment state.

Workflow engine:
- `workflows/state_machine.py` defines deterministic transitions.
- Current transition map advances from `STEP_1` -> `STEP_2` -> `STEP_3` -> `STEP_4` -> `FINAL_PRESSURE` on `BORROWER_REFUSED`.

Service/repo layering:
- Service-level logic under `services/`.
- Repository abstraction under `repositories/`.

### 5.2 `apps/communications` (Outbound channel dispatch)

Main responsibility: send messages/calls through providers.

Structure:
- `sms/`: Heymarket client + SMS service.
- `email/`: Gmail client + email service.
- `voice/`: Telnyx/Twilio clients + voice service.
- `services/communication_router.py`: central channel router.

Router behavior:
- `CommunicationRouter.send_message()` dispatches by channel string (`sms`, `email`, `voice`) to service classes.

### 5.3 `apps/ai` (Intent + response generation)

Main responsibility: classify borrower intent and generate outbound text.

Core modules:
- `intent_detection/intent_analyzer.py`: borrower message intent analysis.
- `message_generation/message_generator.py`: message text generation.
- `services/ai_orchestrator.py`: combines intent analysis with response generation.

Current orchestration behavior:
- `AIOrchestrator.process_borrower_message()`:
  - Detects intent.
  - Builds context from case data.
  - Generates suggested response.
  - Returns confidence-based `requires_human_review`.

### 5.4 `apps/webhooks` (Inbound integration boundary)

Main responsibility: validate and ingest external events.

Key pieces:
- Views: `views/webhook_views.py` defines handlers for SMS, email, voice, CRM.
- Validation: signature and payload validators in `validators/`.
- Routing/orchestration: `services/webhook_processor.py`.
- Channel-specific logic: `handlers/*.py`.

Routing logic:
- `WebhookProcessor.route_webhook(type, payload)` dispatches to the correct handler class by webhook type.
- Also provides queue helpers for async message/transcript processing.

### 5.5 `apps/tasks` (Async and scheduled operations)

Main responsibility: run delayed/background business operations.

Celery configuration:
- `apps/tasks/config.py` defines app + beat schedule.

Scheduled jobs:
- Follow-up messaging windowed by business hours.
- Commitment fulfillment checks.
- Commitment reminders.
- Silence detection.

Async processing:
- `followup_tasks.py` includes:
  - `send_followup_messages()`
  - `process_borrowed_message()`
  - `process_voice_transcript()`

`process_borrowed_message()` currently:
- Loads case + interaction.
- Calls `AIOrchestrator`.
- Stores detected intent/sentiment/confidence metadata on interaction.
- Advances workflow on refusal.
- Creates a payment commitment on promise-to-pay.

### 5.6 `apps/core` (Shared technical utilities)

Main responsibility: cross-cutting concerns used across apps.

Contains:
- Middleware (`middleware/request_logging.py`)
- Validators/decorators/encryption/logging utilities
- Cache service wrapper
- Shared constants
- Management command scaffolding

## 6) Current URL/API Exposure

Mounted at root (`config/urls.py`):
- `/admin/`
- `/api/collections/`
- `/api/communications/`
- `/api/webhooks/`

Current effective exposure state:
- `apps/collections/urls.py` is placeholder (empty patterns).
- `apps/communications/urls.py` is placeholder (empty patterns).
- `apps/ai/urls.py` exists but is not mounted at root.
- `apps/webhooks/urls.py` has webhook routes currently commented out.

Result: while handler/view logic exists, many intended endpoints are not currently reachable via active URL patterns.

## 7) End-to-End Data Flow (As Designed in Code)

Intended loop:
1. External channel or CRM sends webhook payload.
2. Webhook view validates request.
3. Processor routes payload to channel/CRM handler.
4. Handler records/updates case and interactions.
5. For borrower text/transcript, async task is queued.
6. AI analyzes intent and suggests response.
7. Workflow state may transition (e.g., refusal escalation).
8. Next outbound message is routed via communication services.
9. Delivery/reply webhooks update interaction records.
10. Process repeats until resolution.

The implemented modules support this loop conceptually, but full runtime behavior depends on route activation and a few integration fixes.

## 8) Testing and Quality Posture

Test tooling:
- `pytest`, `pytest-django`, `pytest-cov` configured (`pytest.ini`, `conftest.py`).

Test locations:
- `apps/collections/tests/`
- `apps/communications/tests/`
- `apps/ai/tests/`
- `apps/webhooks/tests/`

Code quality tooling declared:
- `black`, `flake8`, `isort`.

Current maturity note:
- Several tests are scaffold-level and should be expanded for webhook integration, workflow transitions, and channel provider contracts.

## 9) Current Implementation Gaps / Risks

Observed from live code structure:
- Webhook URL patterns are commented out in `apps/webhooks/urls.py`.
- Collections/communications API URL modules are placeholders.
- AI intent module references an `intent_types.py` that is not present in `apps/ai/intent_detection/` (only `__init__.py` + `intent_analyzer.py` currently exist).
- No checked-in Django migration files were found under app `migrations/` directories.
- Some provider integrations (especially email/voice paths) appear partial and should be verified end-to-end.

These are engineering gaps, not architectural blockers; the domain decomposition is already aligned with the target platform.

## 10) Mapping to Target Product Vision

Target sequence:
`CRM payment failure` -> `Event ingestion` -> `CollectionCase created` -> `Workflow engine` -> `AI message generator` -> `Channels (Email/SMS/Voice)` -> `Borrower reply` -> `Webhook processing` -> `Intent analysis` -> `State update` -> `Next message`.

Current status by stage:
- **CRM payment failure ingestion**: partially scaffolded in webhooks/handlers.
- **CollectionCase creation/update**: domain model exists; ingestion wiring needs completion.
- **Workflow engine**: implemented with deterministic state machine.
- **AI message generation and intent analysis**: implemented at service level.
- **Channel dispatch**: implemented with router + provider services, but maturity differs by channel.
- **Borrower reply + webhook loop**: logic exists but endpoint exposure currently blocks full loop.
- **State update + next message**: present in tasks/workflow, needs full integration hardening.

## 11) Practical Summary

This project is a strong backend foundation for an AI-assisted debt collection CRM integration:
- Core domain modeling is in place.
- Layer boundaries are clear (webhooks -> tasks -> AI/workflow -> communications).
- Scheduling and async processing strategy is already set.

Main work ahead is integration hardening:
- Activate routes,
- complete ingestion wiring,
- reconcile AI import/contracts,
- add migrations,
- and validate each channel’s provider contract in realistic tests.

