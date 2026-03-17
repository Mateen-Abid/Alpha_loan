# iCollector Alpha Loan: Implemented System and Testing Guide

This document explains what is currently implemented in the project and how to test it end to end.

---

## 1) Implemented Architecture

The project keeps the original app structure:

- `apps/collections`: collection case domain and ledgers
- `apps/communications`: SMS/email/voice dispatch
- `apps/ai`: intent detection and response generation
- `apps/webhooks`: inbound integration endpoints and routing
- `apps/tasks`: asynchronous processing and scheduled jobs
- `apps/core`: shared infrastructure and external integrations

The implementation now wires these layers so a webhook can create/update data, trigger AI, transition workflow, and dispatch follow-up messages.

---

## 2) Core Domain Models in Use

`apps/collections/models/` contains the active domain entities:

- `CollectionCase`
  - tracks borrower/account state, workflow step, automation state
  - includes `partner_row_id`, `automation_status`, `next_action_time`
- `TransactionLedger`
  - stores financial events like `NSF`, `PAYMENT`, etc.
- `InteractionLedger`
  - stores inbound/outbound communication records
  - includes AI metadata (`ai_intent_detected`, sentiment, timestamps)
- `PaymentCommitment`
  - stores promise-to-pay commitments and status progression

Workflow states remain deterministic:
- `STEP_1`, `STEP_2`, `STEP_3`, `STEP_4`, `FINAL_PRESSURE`

Workflow transitions are still governed by `WorkflowStateMachine` in `apps/collections/workflows/state_machine.py`.

---

## 3) Partner Gateway Integration (Implemented)

### API client
Implemented in `apps/core/integrations/icollector_client.py`.

Capabilities:
- builds canonical string:
  - `{timestamp}.{nonce}.{HTTP_METHOD}.{PATH_WITH_QUERY}.{SHA256_HEX_OF_RAW_BODY}`
- computes HMAC SHA256
- sends signed requests with required headers:
  - `Authorization: Bearer <token>`
  - `X-Tenant`
  - `X-Partner-Timestamp`
  - `X-Partner-Nonce`
  - `X-Partner-Signature: sha256=<hex>`

Implemented helper methods:
- `ping()`
- `send_sms()`
- `send_sms_extended()`
- `send_email()`
- `send_email_extended()`
- `get_boards()`
- `get_rows(board_id, limit, offset, group_id)`
- `ingest_row(board_id, group, data, idempotency_key)`
- `update_row()`
- `move_row()`

### Secrets and direction
- `ICOLLECTOR_INBOUND_SECRET`: used to sign requests from this backend to iCollector
- `ICOLLECTOR_OUTBOUND_SECRET`: used to verify webhook signatures received from iCollector

---

## 4) Webhook Layer (Implemented)

### Active routes
`apps/webhooks/urls.py` exposes:
- `POST /api/webhooks/sms/`
- `POST /api/webhooks/email/`
- `POST /api/webhooks/voice/`
- `POST /api/webhooks/crm/`

### Request validation and signature checks
In `apps/webhooks/views/webhook_views.py` and validators:
- payload validation is enforced per endpoint
- partner signature headers are required:
  - `X-Partner-Timestamp`
  - `X-Partner-Nonce`
  - `X-Partner-Signature`
- signature format supports `sha256=<hex>`
- timestamp window validation is enforced (default 300s, configurable by `ICOLLECTOR_SIGNATURE_WINDOW_SECONDS`)

### Processor responsibilities
`apps/webhooks/services/webhook_processor.py` now:
- routes webhook payloads by type
- resolves case by `row_id` or phone/email
- creates inbound `InteractionLedger` entries
- enqueues AI tasks
- processes CRM failed-payment ingestion
- creates NSF ledger entries
- triggers initial outbound message for new/updated CRM cases
- uses idempotency guards for duplicate interactions and duplicate rapid outbound sends

Board family guard is currently enforced by board IDs:
- `70`, `71`, `73`, `74`

---

## 5) AI and Async Processing (Implemented)

### Main tasks
In `apps/tasks/followup_tasks.py`:

- `process_borrower_message(case_id, interaction_id, message, channel)`
  - loads case and interaction
  - calls `AIOrchestrator.process_borrower_message()`
  - stores detected intent and confidence in interaction
  - if intent is `refusal`, advances workflow state
  - if intent is `promise_to_pay`, creates `PaymentCommitment` (idempotent guard)
  - sends AI-generated response through router
- `process_voice_transcript(...)`
  - delegates transcript through the same borrower message AI path
- `send_followup_messages()`
  - queries cases with:
    - `automation_status = ACTIVE`
    - `status = ACTIVE`
    - `next_action_time <= now`
  - generates outbound follow-up message (AI first, fallback text)
  - dispatches through router
  - updates `next_action_time` and `next_followup_at`

### Retry strategy
External dispatch paths use Celery retry-safe settings:
- backoff enabled
- jitter enabled
- bounded retries

---

## 6) Communication Dispatch (Implemented)

`apps/communications/services/communication_router.py` supports:
- `send_message(channel, payload)`
- routes to `SMSService`, `EmailService`, `VoiceService`
- records outbound `InteractionLedger` on successful send

`SMSService` and `EmailService` now use iCollector client methods for outbound calls.

---

## 7) Migrations Added

Collections migration scaffolding is present:
- `apps/collections/migrations/0001_initial.py`
- `apps/collections/migrations/__init__.py`

This includes schema for:
- `CollectionCase`
- `TransactionLedger`
- `InteractionLedger`
- `PaymentCommitment`

---

## 8) Environment Variables Required

At minimum for partner gateway flow:

- `ICOLLECTOR_BASE_URL`
- `ICOLLECTOR_API_TOKEN` (or `ICOLLECTOR_API_KEY`)
- `ICOLLECTOR_TENANT`
- `ICOLLECTOR_INBOUND_SECRET`
- `ICOLLECTOR_OUTBOUND_SECRET`

Also required for runtime:
- DB settings (`DB_*`)
- Redis/Celery settings (`CELERY_*`, `CACHE_LOCATION`)
- AI settings (`OPENAI_API_KEY`, optional model)

Template is in `.env.example`.

---

## 9) Testing Procedure

Use this sequence for safe validation.

### A. Local environment and dependencies
1. Install dependencies:
```bash
pip install -r requirements.txt
```
2. Ensure `.env` has valid partner settings.
3. Run migrations:
```bash
python manage.py migrate
```

### B. Start services
Run in separate terminals:
```bash
python manage.py runserver 0.0.0.0:8000
celery -A config worker -l info
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

Or use Docker:
```bash
docker-compose up -d
```

### C. Static sanity checks
```bash
python -m compileall apps config
python manage.py check
```

### D. Run test suite and lint
```bash
pytest --cov=apps --cov-report=term-missing
flake8 apps config
isort --check-only apps config
```

### E. Partner gateway connectivity tests
Use `ICollectorClient` in Django shell:
```bash
python manage.py shell
```
```python
from apps.core.integrations import ICollectorClient
client = ICollectorClient()
print(client.ping())
print(client.get_boards())
```

Expected:
- no signature/auth failures
- tenant-scoped board list returned

### F. CRM ingestion flow test
POST test payload to local CRM webhook endpoint:
`/api/webhooks/crm/`

Payload example:
```json
{
  "row_id": "12001",
  "board_id": 70,
  "phone": "+15145551212",
  "email": "client@example.com",
  "failed_payment_amount": "120.50",
  "return_reason": "nsf"
}
```

Verify in DB:
- `CollectionCase` created/updated with `partner_row_id`
- `TransactionLedger` NSF row created
- outbound `InteractionLedger` record created

### G. Inbound message -> AI -> workflow transition
POST SMS webhook to `/api/webhooks/sms/` with a refusal message.

Verify:
- inbound `InteractionLedger` created
- Celery processes `process_borrower_message`
- `ai_intent_detected` populated
- case workflow step advances on refusal

Repeat with promise-to-pay text and verify `PaymentCommitment` creation.

### H. Scheduler behavior test
Set a case:
- `automation_status = ACTIVE`
- `next_action_time <= now`

Trigger:
```bash
python manage.py shell
```
```python
from apps.tasks.followup_tasks import send_followup_messages
send_followup_messages.delay()
```

Verify:
- outbound interaction created
- case `next_action_time` moved forward

### I. Signature negative tests
For each webhook endpoint:
- missing partner signature headers -> expect `401`
- invalid signature -> expect `401`
- stale timestamp outside allowed window -> expect `401`

### J. Idempotency safety checks
Replay same webhook payload (`message_id`/`call_id` same) and verify:
- processor returns idempotent success
- duplicate interactions are not created

---

## 10) Known Follow-up Enhancements

Recommended next hardening items:
- nonce replay persistence store (not just timestamp window)
- stricter event-type routing using `X-Partner-Event`
- keyword-based board-family validation in addition to board ID allowlist
- broaden integration tests around partner API idempotency keys

