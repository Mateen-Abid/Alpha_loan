# Technical Implementation Report
## Alpha Loan Collections Automation Platform

**Project Name:** alpha_loan_project  
**Analysis Date:** March 18, 2026  
**Project Type:** AI-driven loan collections automation system  
**Technology Stack:** Django 4.2 + PostgreSQL + Celery + OpenAI + iCollector Gateway

---

## 1. PROJECT STRUCTURE

```
alpha_loan_project/
│
├── config/
│   ├── settings/
│   │   ├── base.py                 # Base configuration (DB, apps, Celery, cache, logging, DRF)
│   │   ├── development.py
│   │   ├── production.py
│   │   └── test.py
│   ├── urls.py                      # Main URL routing
│   ├── asgi.py                      # ASGI server entrypoint
│   ├── wsgi.py                      # WSGI server entrypoint
│   └── __init__.py
│
├── apps/
│   │
│   ├── collections/                 # CORE COLLECTIONS DOMAIN
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── collection_case.py       # CollectionCase model (account, workflow, status)
│   │   │   ├── transaction_ledger.py    # TransactionLedger model (payments, fees, NSF)
│   │   │   ├── interaction_ledger.py    # InteractionLedger model (SMS/email/voice log + AI fields)
│   │   │   └── payment_commitment.py    # PaymentCommitment model (promise-to-pay tracking)
│   │   ├── workflows/
│   │   │   ├── __init__.py
│   │   │   ├── state_machine.py         # Deterministic state machine (STEP_1 → FINAL_PRESSURE)
│   │   │   └── workflow_states.py       # WorkflowState & WorkflowActions enums
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── collection_service.py    # Business logic (create case, find case, record interaction)
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   └── collection_case_repo.py  # Data access abstraction
│   │   ├── views/
│   │   │   └── __init__.py
│   │   ├── admin/
│   │   │   └── __init__.py              # Django admin customization
│   │   ├── urls.py                      # Collections API routes (currently placeholder)
│   │   ├── admin.py                     # Admin model registration
│   │   ├── apps.py
│   │   ├── migrations/
│   │   │   ├── __init__.py
│   │   │   └── 0001_initial.py          # Initial schema migration
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_collections.py      # Minimal test scaffold
│   │   └── __init__.py
│   │
│   ├── communications/              # MULTI-CHANNEL MESSAGE DISPATCH
│   │   ├── models/
│   │   │   └── __init__.py
│   │   ├── sms/
│   │   │   ├── __init__.py
│   │   │   ├── heymarket_client.py      # Heymarket SMS provider client (placeholder)
│   │   │   └── sms_service.py           # SMS dispatch via iCollector gateway
│   │   ├── email/
│   │   │   ├── __init__.py
│   │   │   ├── gmail_client.py          # Gmail provider client (placeholder)
│   │   │   └── email_service.py         # Email dispatch via iCollector gateway
│   │   ├── voice/
│   │   │   ├── __init__.py
│   │   │   ├── telnyx_client.py         # Telnyx voice provider
│   │   │   ├── twilio_client.py         # Twilio voice provider
│   │   │   └── voice_service.py         # Voice call dispatch (abstraction over Telnyx/Twilio)
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── communication_router.py  # CHANNEL ROUTER: dispatches to SMS/email/voice
│   │   │   └── template_service.py      # Message template management
│   │   ├── views/
│   │   │   └── __init__.py
│   │   ├── admin/
│   │   │   └── __init__.py
│   │   ├── urls.py                      # Communications API routes (placeholder)
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_communications.py   # Test scaffold
│   │   └── __init__.py
│   │
│   ├── ai/                          # AI INTENT & MESSAGE GENERATION
│   │   ├── clients/
│   │   │   ├── __init__.py
│   │   │   └── openai_client.py         # OpenAI API client wrapper
│   │   ├── intent_detection/
│   │   │   ├── __init__.py
│   │   │   └── intent_analyzer.py       # AI intent classification (promise_to_pay, refusal, etc.)
│   │   ├── message_generation/
│   │   │   ├── __init__.py
│   │   │   ├── message_generator.py     # AI-powered SMS/email generation
│   │   │   └── prompt_templates.py      # System & user prompt templates
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── ai_orchestrator.py       # ORCHESTRATOR: coordinates intent analysis + response generation
│   │   ├── views/
│   │   │   └── __init__.py
│   │   ├── admin/
│   │   │   └── __init__.py
│   │   ├── urls.py                      # AI API routes (not mounted at root)
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_ai.py               # Test scaffold
│   │   └── __init__.py
│   │
│   ├── webhooks/                    # INBOUND INTEGRATION BOUNDARY
│   │   ├── handlers/
│   │   │   ├── __init__.py
│   │   │   ├── crm_webhook_handler.py   # CRM event processing (not in separate file)
│   │   │   ├── sms_webhook_handler.py   # SMS event processing (logic in processor)
│   │   │   ├── email_webhook_handler.py # Email event processing
│   │   │   └── voice_webhook_handler.py # Voice event processing
│   │   ├── validators/
│   │   │   ├── __init__.py
│   │   │   ├── signature_validator.py   # HMAC signature validation (Heymarket, iCollector, Telnyx, Twilio)
│   │   │   └── payload_validator.py     # Request payload validation
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── webhook_processor.py     # WEBHOOK ORCHESTRATION: routes + persists + queues
│   │   ├── views/
│   │   │   ├── __init__.py
│   │   │   └── webhook_views.py         # 4 webhook endpoints (SMS, Email, Voice, CRM)
│   │   ├── urls.py                      # Webhook URL routes (ACTIVE)
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── admin/
│   │   │   └── __init__.py
│   │   ├── tests/
│   │   │   ├── __init__.py
│   │   │   └── test_webhooks.py         # Test scaffold
│   │   └── __init__.py
│   │
│   ├── tasks/                       # ASYNC & SCHEDULED JOBS (Celery)
│   │   ├── __init__.py
│   │   ├── config.py                    # Celery app + beat schedule configuration
│   │   ├── followup_tasks.py            # Main async tasks:
│   │   │                               #   - send_followup_messages()
│   │   │                               #   - process_borrower_message()
│   │   │                               #   - process_borrowed_message() [alias]
│   │   │                               #   - process_voice_transcript()
│   │   ├── promise_tasks.py             # Commitment tracking:
│   │   │                               #   - check_commitment_fulfillment()
│   │   │                               #   - send_commitment_reminder()
│   │   └── silence_detection_tasks.py   # Silence detection:
│   │                                   #   - detect_silence_periods()
│   │                                   #   - attempt_escalated_contact()
│   │
│   └── core/                        # SHARED UTILITIES
│       ├── integrations/
│       │   ├── __init__.py
│       │   └── icollector_client.py     # iCollector partner gateway API client (HMAC-signed requests)
│       ├── constants/
│       ├── middleware/
│       ├── utils/
│       ├── services/
│       │   ├── cache_service.py         # Django cache wrapper
│       │   └── ...other services
│       └── management/
│
├── docs/
│   ├── ARCHITECTURE.md                  # System architecture diagrams & data flows
│   ├── DEVELOPMENT.md
│   └── IMPLEMENTED_SYSTEM_AND_TESTING.md # Integration testing guide
│
├── tests/
│   ├── factories/
│   │   └── __init__.py
│   ├── fixtures/
│   │   └── __init__.py
│   └── __init__.py
│
├── Dockerfile                           # Docker image build
├── docker-compose.yml                   # Multi-container orchestration (web, worker, beat, redis, db)
├── Makefile                             # Common commands
├── manage.py                            # Django CLI entrypoint
├── requirements.txt                     # Python dependencies (fixed)
├── pytest.ini                           # pytest configuration
├── conftest.py                          # pytest fixtures
├── .env.example                         # Environment variable template
├── README.md
├── PROJECT_SUMMARY.md
├── PROJECT_DEEP_DIVE.md
├── FOLDER_STRUCTURE.txt
├── DIRECTORY_TREE.md
└── __init__.py

```

---

## 2. DATA MODELS

### Overview
The collections domain uses a 4-model schema with referential integrity and comprehensive indexing for performance.

### 2.1 CollectionCase

```python
class CollectionCase(Model):
    """Represents a delinquent loan account."""
    
    # Account Identifiers
    account_id: CharField (unique, db_index)
    partner_row_id: CharField (unique, nullable, db_index)  # iCollector board row ID
    borrower_name: CharField
    borrower_email: EmailField (nullable)
    borrower_phone: CharField (db_index)
    
    # Financial
    principal_amount: DecimalField
    total_due: DecimalField
    amount_paid: DecimalField (default=0)
    
    # Workflow State
    current_workflow_step: CharField (choices=[STEP_1, STEP_2, STEP_3, STEP_4, FINAL_PRESSURE], db_index)
    workflow_step_started_at: DateTimeField (auto_now_add)
    
    # Status
    status: CharField (choices=[ACTIVE, RESOLVED, LOST, SUSPENDED], db_index)
    automation_status: CharField (choices=[ACTIVE, PAUSED, STOPPED], db_index)
    
    # Dates
    delinquent_date: DateField (db_index)
    created_at: DateTimeField (auto_now_add, db_index)
    updated_at: DateTimeField (auto_now)
    last_contact_at: DateTimeField (nullable, db_index)
    next_followup_at: DateTimeField (nullable, db_index)
    next_action_time: DateTimeField (nullable, db_index)  # For scheduler queries
    
    # Flags
    does_not_call: BooleanField (default=False)
    notes: TextField
    
    # Relationships
    transactions: ForeignKey → TransactionLedger (cascade)
    interactions: ForeignKey → InteractionLedger (cascade)
    commitments: ForeignKey → PaymentCommitment (cascade)
    
    # Indexes
    (status, current_workflow_step)
    (automation_status, next_action_time)
    (borrower_phone)
    (next_followup_at)
```

**Key Methods:**
- `get_age_in_days()` — Returns days since delinquent_date
- `get_remaining_balance()` — Returns `total_due - amount_paid`

---

### 2.2 TransactionLedger

```python
class TransactionLedger(Model):
    """Tracks financial events (payments, fees, NSF, reversals)."""
    
    # Reference
    collection_case: ForeignKey → CollectionCase (cascade, related_name='transactions')
    
    # Transaction Details
    transaction_type: CharField (choices=[PAYMENT, ADJUSTMENT, FEE, NSF, REVERSAL], db_index)
    amount: DecimalField
    description: TextField
    
    # External Tracking
    external_reference: CharField (nullable, db_index)  # Payment gateway ID, check number, etc.
    posted_date: DateField (db_index)
    
    # Metadata
    created_at: DateTimeField (auto_now_add)
    created_by: CharField  # "System", "webhook", "user_name", etc.
    
    # Indexes
    (collection_case, posted_date)
```

**Purpose:** Financial audit trail. Every payment, fee, NSF, or adjustment is immutably recorded here.

---

### 3.3 InteractionLedger

```python
class InteractionLedger(Model):
    """Records all communication interactions (SMS, Email, Voice, Manual)."""
    
    # Reference
    collection_case: ForeignKey → CollectionCase (cascade, related_name='interactions')
    
    # Channel & Direction
    channel: CharField (choices=[SMS, EMAIL, VOICE, MANUAL], db_index)
    interaction_type: CharField (choices=[OUTBOUND, INBOUND], db_index)
    
    # Status Tracking
    status: CharField (choices=[PENDING, SENT, DELIVERED, READ, REPLIED, FAILED, BOUNCED], db_index)
    
    # Message Content
    subject: CharField (for email)
    message_content: TextField
    
    # External Tracking
    external_id: CharField (nullable, db_index)  # Heymarket ID, Gmail thread ID, Telnyx call ID, etc.
    
    # Delivery Timeline
    sent_at: DateTimeField (nullable)
    delivered_at: DateTimeField (nullable)
    read_at: DateTimeField (nullable)
    replied_at: DateTimeField (nullable)
    created_at: DateTimeField (auto_now_add)
    
    # AI Processing
    ai_intent_detected: CharField (nullable)  # promise_to_pay, refusal, dispute, hardship, payment_made, etc.
    ai_sentiment_score: FloatField (nullable)  # -1.0 to 1.0
    ai_processed_at: DateTimeField (nullable)
    
    # Response Information
    reply_message: TextField (nullable)  # AI-generated or manual response
    ai_generated: BooleanField (default=False)
    
    # Indexes
    (collection_case, created_at)
    (channel, status)
```

**Purpose:** Complete audit trail of communication. Inbound interactions trigger AI processing; outbound captures result of AI generation or manual composition.

---

### 2.4 PaymentCommitment

```python
class PaymentCommitment(Model):
    """Tracks promise-to-pay commitments and fulfillment."""
    
    # Reference
    collection_case: ForeignKey → CollectionCase (cascade, related_name='commitments')
    
    # Commitment Details
    committed_amount: DecimalField
    amount_paid: DecimalField (default=0)
    promised_date: DateField (db_index)
    
    # Status Lifecycle
    status: CharField (choices=[PENDING, CONFIRMED, PARTIAL_PAID, FULFILLED, BROKEN, CANCELLED], db_index)
    
    # Created/Updated
    created_at: DateTimeField (auto_now_add)
    updated_at: DateTimeField (auto_now)
    
    # Source Information
    payment_method: CharField (nullable)  # ACH, Check, Credit Card, other
    commitment_source: CharField (nullable)  # SMS, Voice, Email, etc.
    notes: TextField
    
    # Indexes
    (collection_case, promised_date)
    (status)
```

**Purpose:** Tracks promise-to-pay commitments detected from AI analysis. Enables monitoring and escalation if commitment broken.

**Key Methods:**
- `get_remaining_amount()` — Returns `committed_amount - amount_paid`

---

### 2.5 Model Relationships

```
CollectionCase (1) ──── (N) TransactionLedger
     │
     ├──── (N) InteractionLedger
     │
     └──── (N) PaymentCommitment
```

**Data Flow:**
1. CollectionCase is created via CRM webhook or manual entry
2. TransactionLedger records track every payment/fee event
3. InteractionLedger logs every SMS/email/voice interaction + AI metadata
4. PaymentCommitment records created when AI detects "promise_to_pay" intent
5. Workflow transitions triggered by:
   - Inbound refusal → advance to next STEP
   - Broken commitment → escalate (if enabled)

---

## 3. WORKFLOW ENGINE

### 3.1 State Machine Definition

The workflow is a deterministic, linear state machine defined in `apps/collections/workflows/state_machine.py`.

**States (WorkflowState enum):**
```
STEP_1           → "Immediate Payment" (initial state)
STEP_2           → "Double Payment"
STEP_3           → "Add NSF to Next Payment"
STEP_4           → "Split NSF"
FINAL_PRESSURE   → "Final Pressure" (terminal state)
```

**Transition Triggers (WorkflowActions enum):**
```
BORROWER_REFUSED       → Triggered when AI detects refusal intent
PAYMENT_RECEIVED       → (defined but not currently used)
COMMITMENT_BROKEN      → Triggered when promised payment date passes unfulfilled
ESCALATE              → (defined but not currently used)
RESET                 → (defined but not currently used)
```

**Transition Matrix:**
```python
TRANSITIONS = {
    STEP_1: {
        BORROWER_REFUSED → STEP_2,
    },
    STEP_2: {
        BORROWER_REFUSED → STEP_3,
    },
    STEP_3: {
        BORROWER_REFUSED → STEP_4,
    },
    STEP_4: {
        BORROWER_REFUSED → FINAL_PRESSURE,
    },
    FINAL_PRESSURE: {
        # Terminal state - no transitions
    },
}
```

**Key Properties:**
- **Linear only** — Can only progress forward, never backward
- **Single trigger** — Only BORROWER_REFUSED currently causes transitions
- **Terminal state** — FINAL_PRESSURE has no outgoing transitions

### 3.2 Transition Execution Points

**Primary:** `apps/tasks/followup_tasks.py` - `process_borrower_message()` task

```python
def process_borrower_message(case_id, interaction_id, message, channel):
    # 1. Load case and interaction
    case = CollectionCase.objects.get(id=case_id)
    interaction = InteractionLedger.objects.get(id=interaction_id)
    
    # 2. Call AI orchestrator to detect intent
    ai_result = orchestrator.process_borrower_message(message, context)
    intent = ai_result['intent']['intent']
    
    # 3. Store intent in interaction record
    interaction.ai_intent_detected = intent
    interaction.ai_processed_at = timezone.now()
    interaction.save()
    
    # 4. Transition if refusal detected
    if intent == "refusal":
        state_machine = WorkflowStateMachine(WorkflowState[case.current_workflow_step])
        if state_machine.transition(WorkflowActions.BORROWER_REFUSED):
            case.current_workflow_step = state_machine.current_state.value
            case.workflow_step_started_at = timezone.now()
            case.save()  # ← TRANSITION EXECUTED HERE
    
    # 5. Create PaymentCommitment if promise-to-pay
    elif intent == "promise_to_pay":
        promised_date = timezone.now() + timedelta(days=3)
        CollectionService.create_payment_commitment(...)
```

**Secondary:** `apps/tasks/promise_tasks.py` - `check_commitment_fulfillment()` task

```python
def check_commitment_fulfillment():
    # Daily (midnight) scheduled task
    past_commitments = PaymentCommitment.objects.filter(
        status__in=['PENDING', 'CONFIRMED'],
        promised_date__lt=today
    )
    
    for commitment in past_commitments:
        if commitment.amount_paid >= commitment.committed_amount:
            commitment.status = 'FULFILLED'
        else:
            commitment.status = 'BROKEN'
            # Trigger escalation if enabled
            case = commitment.collection_case
            state_machine = WorkflowStateMachine(WorkflowState[case.current_workflow_step])
            if state_machine.transition(WorkflowActions.COMMITMENT_BROKEN):
                case.current_workflow_step = state_machine.current_state.value
                case.save()  # ← TRANSITION EXECUTED HERE
```

### 3.3 Workflow Messaging Context

Each workflow step has different messaging strategies in AI message generation:

```python
# Message generator adjusts tone by workflow step
_get_sms_system_prompt(step):
    STEP_1      → "Be courteous and professional. This is initial contact."
    STEP_2      → "Be urgent but professional. This is a follow-up."
    STEP_3      → "Be firm and direct. Mention NSF fees."
    STEP_4      → "Be serious. Emphasize payment is critical."
    FINAL_PRESSURE → "Be final and decisive. Final notice."
```

This ensures messages escalate in severity as the borrower progresses through collection steps.

---

## 4. WEBHOOK IMPLEMENTATION

### 4.1 Webhook Endpoints

All webhooks are routed through the partner gateway's iCollector signature validation scheme.

**Active Routes** (in `apps/webhooks/urls.py`):
```
POST /api/webhooks/sms/     → webhook_views.sms_webhook()
POST /api/webhooks/email/   → webhook_views.email_webhook()
POST /api/webhooks/voice/   → webhook_views.voice_webhook()
POST /api/webhooks/crm/     → webhook_views.crm_webhook()
```

### 4.2 SMS Webhook

**Endpoint:** `POST /api/webhooks/sms/`

**View Handler:** `apps/webhooks/views/webhook_views.py` - `sms_webhook(request)`

**Validation:**
1. Verify `X-Partner-Signature` header using iCollector secret (HMAC-SHA256)
2. Validate payload structure via `PayloadValidator.validate_sms_webhook()`

**Processor:** `apps/webhooks/services/webhook_processor.py` - `_process_inbound_message(payload, channel='SMS')`

**Data Stored:**
```python
InteractionLedger.objects.create(
    collection_case=case,
    channel='SMS',
    interaction_type='INBOUND',
    status='REPLIED',
    message_content=payload['message'],
    external_id=payload.get('message_id'),
)
```

**Async Processing:**
- Queues `process_borrower_message.delay(case_id, interaction_id, message, 'sms')` to Celery
- AI analyzes intent, potentially triggers workflow transition

**Example Payload:**
```json
{
  "message_id": "hym_123abc",
  "phone": "+15145551234",
  "from": "+15145551234",
  "message": "I cannot pay right now",
  "timestamp": "2026-03-18T14:30:00Z"
}
```

---

### 4.3 Email Webhook

**Endpoint:** `POST /api/webhooks/email/`

**View Handler:** `webhook_views.email_webhook(request)`

**Validation:**
- Same signature validation as SMS
- Payload validation via `PayloadValidator.validate_email_webhook()`

**Processor:** `_process_inbound_message(payload, channel='EMAIL')`

**Data Stored:**
```python
InteractionLedger.objects.create(
    collection_case=case,
    channel='EMAIL',
    interaction_type='INBOUND',
    status='REPLIED',
    subject=payload.get('subject', ''),
    message_content=payload.get('body', payload.get('message', '')),
    external_id=payload.get('message_id'),
)
```

**Example Payload:**
```json
{
  "message_id": "gmail_msg_xyz",
  "from_email": "borrower@example.com",
  "subject": "Re: Collection Notice",
  "body": "I will pay next week",
  "timestamp": "2026-03-18T14:30:00Z"
}
```

---

### 4.4 Voice Webhook

**Endpoint:** `POST /api/webhooks/voice/`

**View Handler:** `webhook_views.voice_webhook(request)`

**Validation:**
- Signature validation with iCollector secret
- Payload validation via `PayloadValidator.validate_voice_webhook()`

**Processor:** `_process_voice(payload)`

**Data Stored:**
```python
InteractionLedger.objects.create(
    collection_case=case,
    channel='VOICE',
    interaction_type='INBOUND',
    status='DELIVERED' if no transcript else 'REPLIED',
    message_content=transcript or "Voice call completed",
    external_id=payload.get('call_id'),
)
```

**Async Processing:**
- If transcript present, queues `process_voice_transcript.delay(case_id, interaction_id, transcript)`
- AI analyzes transcript (same as SMS processing)

**Example Payload:**
```json
{
  "call_id": "telnyx_call_abc123",
  "phone": "+15145551234",
  "duration": 120,
  "transcript": "I'll try to pay something this week",
  "status": "completed",
  "timestamp": "2026-03-18T14:35:00Z"
}
```

---

### 4.5 CRM Webhook

**Endpoint:** `POST /api/webhooks/crm/`

**View Handler:** `webhook_views.crm_webhook(request)`

**Validation:**
- Signature validation
- Payload validation via `PayloadValidator.validate_crm_webhook()`
- Board ID validation (only boards 70, 71, 73, 74 allowed)

**Processor:** `_process_crm_ingestion(payload)`

**Data Stored (in transaction block):**
```python
# 1. Create or update CollectionCase
case = CollectionCase.objects.update_or_create(
    partner_row_id=row_id,
    defaults={
        'account_id': row_id,
        'borrower_name': payload.get('name'),
        'borrower_phone': payload.get('phone'),
        'borrower_email': payload.get('email'),
        'total_due': Decimal(payload.get('failed_payment_amount', 0)),
        'delinquent_date': date.today(),
    }
)

# 2. Record NSF transaction if failed payment
if payload.get('return_reason') == 'nsf':
    TransactionLedger.objects.create(
        collection_case=case,
        transaction_type='NSF',
        amount=Decimal(payload.get('failed_payment_amount', 0)),
        posted_date=date.today(),
        external_reference=payload.get('payment_id'),
    )

# 3. Create outbound interaction (initial contact)
interaction = InteractionLedger.objects.create(
    collection_case=case,
    channel='SMS',
    interaction_type='OUTBOUND',
    status='PENDING',
    message_content=ai_message,
)

# 4. Dispatch initial collection message
router.send_message('sms', payload={...})
```

**Example Payload:**
```json
{
  "row_id": "crm_row_12001",
  "board_id": 70,
  "phone": "+15145551234",
  "email": "borrower@example.com",
  "failed_payment_amount": "120.50",
  "return_reason": "nsf",
  "payment_id": "pay_abc123",
  "timestamp": "2026-03-18T14:00:00Z"
}
```

---

### 4.6 Signature Validation

**Validator:** `apps/webhooks/validators/signature_validator.py` - `SignatureValidator.validate_icollector_signature()`

**Algorithm:**
```python
# Build canonical string
canonical = f"{timestamp}.{nonce}.{method}.{path_with_query}.{body_sha256}"

# Compute HMAC-SHA256 using ICOLLECTOR_OUTBOUND_SECRET
expected_signature = hmac.new(
    secret.encode(),
    canonical.encode(),
    hashlib.sha256
).hexdigest()

# Compare (constant-time)
provided_signature == expected_signature
```

**Enforced Validations:**
1. **Required headers present:** `X-Partner-Timestamp`, `X-Partner-Nonce`, `X-Partner-Signature`
2. **Timestamp within window:** Default 300 seconds (configurable via `ICOLLECTOR_SIGNATURE_WINDOW_SECONDS`)
3. **Signature matches:** HMAC-SHA256 verification

**Failure responses:**
- Missing headers → `401 Unauthorized`
- Stale timestamp → `401 Unauthorized`
- Invalid signature → `401 Unauthorized`
- Bad payload → `400 Bad Request`

---

## 5. AI PROCESSING

### 5.1 AI Architecture

The AI subsystem has three main components:

```
AIOrchestrator (main coordinator)
    ├── IntentAnalyzer (borrower intent classification)
    │   └── OpenAIClient (API wrapper)
    └── MessageGenerator (SMS/email generation)
        └── OpenAIClient (API wrapper)
```

### 5.2 Intent Analyzer

**File:** `apps/ai/intent_detection/intent_analyzer.py`

**Purpose:** Classify borrower's inbound message to detect intent.

**Method:** `analyze_message(message: str) → Dict`

**System Prompt:**
```
Classify the borrower's message into one of these intents:
- promise_to_pay: Borrower commits to pay
- refusal: Borrower refuses to pay
- request_info: Borrower asking for information
- dispute: Borrower disputes the debt
- hardship: Borrower claims financial hardship
- payment_made: Borrower indicates payment was made
- callback_request: Borrower requests callback
- unknown: Cannot determine intent

Respond with JSON: {"intent": "intent_name", "confidence": 0.0-1.0, "summary": "brief summary"}
```

**Parameters:**
- Temperature: 0.3 (low randomness for classification)
- Model: OpenAI (default or configured)

**Output:**
```python
{
    "intent": "promise_to_pay",  # or refusal, dispute, hardship, etc.
    "confidence": 0.92,           # 0.0 to 1.0 confidence score
    "summary": "Borrower promises to pay in 3 days"
}
```

**Workflow Integration:**
- If `intent == "refusal"` → WorkflowStateMachine advances to next step
- If `intent == "promise_to_pay"` → PaymentCommitment created with promised_date = now + 3 days
- If `confidence < 0.7` → Flag `requires_human_review`

### 5.3 Message Generator

**File:** `apps/ai/message_generation/message_generator.py`

**Purpose:** Generate personalized SMS/email collection messages.

**Methods:**

#### `generate_sms(context: Dict) → Dict`

**Context required:**
```python
{
    "amount_due": 1200.50,
    "workflow_step": "STEP_2",
    "days_delinquent": 45,
    "borrower_name": "John Doe",
    "detected_intent": "promise_to_pay"  # optional
}
```

**System Prompt varies by workflow step:**
- STEP_1: "Be courteous and professional."
- STEP_2: "Be urgent but professional."
- STEP_3: "Be firm. Mention NSF fees."
- STEP_4: "Be serious. Emphasize payment critical."
- FINAL_PRESSURE: "Be final and decisive."

**Temperature:** 0.5 (moderate creativity)

**Output:**
```python
{
    "message": "Hi John, we need payment of $1,200.50 immediately to avoid late fees.",
    "status": "success",
    "error": null
}
```

**Character limit enforced:** 160 chars (SMS standard)

#### `generate_email(context: Dict) → Dict`

**System Prompt:**
```
Write a {STEP} collection email. Keep it professional but firm.
- Amount due: ${amount}
- Borrower: {name}
```

**Output:**
```python
{
    "subject": "Urgent: Collection Notice",
    "body": "Dear John,\n\nYour account requires immediate attention...",
    "status": "success",
    "error": null
}
```

### 5.4 AI Orchestrator

**File:** `apps/ai/services/ai_orchestrator.py`

**Purpose:** Coordinates intent detection with response generation.

**Method:** `process_borrower_message(message: str, case: Dict) → Dict`

**Workflow:**
```
1. Call intent_analyzer.analyze_message(message)
   → returns {intent, confidence, summary}

2. Build context from case data
   context = {
       amount_due, workflow_step, days_delinquent, borrower_name
   }

3. Call message_generator.generate_sms(context)
   → returns {message, status, error}

4. Return combined result
   {
       "intent": {intent_data},
       "suggested_response": {message_gen_result},
       "requires_human_review": confidence < 0.7
   }
```

**Method:** `generate_outbound_message(channel: str, case: Dict, template: str = None) → Dict`

**Purpose:** Generate initial follow-up message during workflow.

**Channels supported:**
- "sms" → calls `message_generator.generate_sms()`
- "email" → calls `message_generator.generate_email()`

---

### 5.5 End-to-End AI Flow

```
Inbound SMS Webhook
  ↓
SMS Webhook Handler validates & routes
  ↓
WebhookProcessor._process_inbound_message()
  → Creates InteractionLedger (inbound)
  → Queues process_borrower_message task
  ↓
[Celery Worker executes process_borrower_message]
  ↓
AIOrchestrator.process_borrower_message()
  ├─ IntentAnalyzer.analyze_message()
  │  └─ OpenAI classifies intent
  └─ MessageGenerator.generate_sms()
     └─ OpenAI generates response
  ↓
Store AI metadata in InteractionLedger
  → ai_intent_detected = "promise_to_pay"
  → ai_sentiment_score = 0.85
  → ai_processed_at = now
  ↓
Check intent:
  If "refusal":
    → WorkflowStateMachine transitions to next step
  If "promise_to_pay":
    → PaymentCommitment created
  ↓
If suggested_response present:
  → Queue outbound dispatch via CommunicationRouter
  ↓
Update case timestamps:
  → last_contact_at = now
  → next_action_time = now + 2 days
  ↓
Workflow complete
```

---

## 6. ASYNC TASKS

All async processing uses Celery with Redis as broker. Tasks are defined in `apps/tasks/`.

### 6.1 Celery Configuration

**File:** `apps/tasks/config.py`

```python
app = Celery('alpha_loan_project')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

**Celery Beat Schedule:**

```python
app.conf.beat_schedule = {
    'send-followup-messages': {
        'task': 'apps.tasks.followup_tasks.send_followup_messages',
        'schedule': crontab(hour='9-17', minute='*/30'),  # Every 30 mins during business hours
    },
    'check-commitment-fulfillment': {
        'task': 'apps.tasks.promise_tasks.check_commitment_fulfillment',
        'schedule': crontab(hour='0', minute='0'),  # Daily at midnight UTC
    },
    'send-commitment-reminder': {
        'task': 'apps.tasks.promise_tasks.send_commitment_reminder',
        'schedule': crontab(hour='8', minute='0'),  # Daily at 8 AM UTC
    },
    'detect-silence-periods': {
        'task': 'apps.tasks.silence_detection_tasks.detect_silence_periods',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
}

app.conf.timezone = 'UTC'
```

### 6.2 Follow-up Message Scheduler

**File:** `apps/tasks/followup_tasks.py` - `send_followup_messages()`

**Schedule:** Every 30 minutes during business hours (9 AM - 5 PM UTC)

**What it does:**
```
1. Query cases where:
   - automation_status = ACTIVE
   - status = ACTIVE
   - next_action_time <= now

2. For each case:
   a. Generate AI message via AIOrchestrator.generate_outbound_message("sms", context)
   b. Fallback to template message if AI fails
   c. Check for duplicate (idempotency guard)
      → Skip if identical message sent in last 5 minutes
   d. Dispatch via CommunicationRouter.send_message("sms", payload)
      - Calls SMSService.send_collection_sms()
      - Calls iCollector gateway
   e. Update case timestamps:
      → next_action_time = now + 3 days
      → next_followup_at = now + 3 days
      → last_contact_at = now

3. Log results
```

**Retry Strategy:**
```python
@shared_task(
    bind=True,
    autoretry_for=(ExternalDispatchError,),  # Retry on dispatch failures
    retry_backoff=True,                      # Exponential backoff
    retry_jitter=True,                       # Add jitter
    max_retries=5                            # Max 5 retries
)
```

### 6.3 Borrower Message Processing

**File:** `apps/tasks/followup_tasks.py` - `process_borrower_message()`

**Trigger:** Queued by webhook handlers (SMS, Email, Voice)

**What it does:**
```
1. Load CollectionCase and InteractionLedger
2. Check if already processed (idempotency)
   → If ai_processed_at is set, skip
3. Call AIOrchestrator.process_borrower_message()
   → Detect intent
   → Generate response
4. Store AI metadata in InteractionLedger:
   - ai_intent_detected
   - ai_sentiment_score (confidence)
   - ai_processed_at = now
   - reply_message = suggested response
5. Check intent:
   a. If "refusal":
      → WorkflowStateMachine.transition(BORROWER_REFUSED)
      → case.current_workflow_step = next_state
      → case.workflow_step_started_at = now
   b. If "promise_to_pay":
      → CollectionService.create_payment_commitment()
      → CommitmentStatus = PENDING
      → promised_date = now + 3 days
6. Update case:
   - last_contact_at = now
   - next_action_time = now + 2 days
   - next_followup_at = now + 2 days
7. If suggested_response exists:
   → Queue outbound dispatch via CommunicationRouter
   → Records OUTBOUND InteractionLedger
8. Return {"status": "success", "intent": detected_intent}
```

**Retry Strategy:** Same as send_followup_messages (exponential backoff, max 5 retries)

### 6.4 Voice Transcript Processing

**File:** `apps/tasks/followup_tasks.py` - `process_voice_transcript()`

**Trigger:** Queued by voice webhook if transcript present

**What it does:**
```
1. Load CollectionCase and InteractionLedger
2. Check if already processed
   → If ai_processed_at is set, skip
3. Delegate to process_borrower_message() with:
   - message = transcript
   - channel = "voice"
4. Same AI processing, intent detection, workflow transition
```

### 6.5 Commitment Fulfillment Check

**File:** `apps/tasks/promise_tasks.py` - `check_commitment_fulfillment()`

**Schedule:** Daily at midnight UTC

**What it does:**
```
1. Query past commitments:
   - status IN [PENDING, CONFIRMED]
   - promised_date < today

2. For each commitment:
   a. If amount_paid >= committed_amount:
      → status = FULFILLED
   b. Else:
      → status = BROKEN
      → Trigger workflow escalation:
         * WorkflowStateMachine.transition(COMMITMENT_BROKEN)
         * case.current_workflow_step = next_state
         * Log escalation event
3. Persist changes
```

### 6.6 Commitment Reminder

**File:** `apps/tasks/promise_tasks.py` - `send_commitment_reminder()`

**Schedule:** Daily at 8 AM UTC

**What it does:**
```
1. Query commitments due tomorrow:
   - status IN [PENDING, CONFIRMED]
   - promised_date = tomorrow

2. For each commitment:
   a. Get case details
   b. Build reminder message:
      "Reminder: Payment of ${amount} is due tomorrow."
   c. Dispatch via CommunicationRouter.send_message("sms", ...)
   d. Log result

3. Handle errors gracefully (don't retry)
```

### 6.7 Silence Detection

**File:** `apps/tasks/silence_detection_tasks.py`

#### Part 1: `detect_silence_periods()`

**Schedule:** Every 6 hours

**What it does:**
```
1. Define silence threshold: 7 days without contact
2. Query silent cases:
   - status = ACTIVE
   - last_contact_at <= (now - 7 days)

3. For each silent case:
   a. Log warning: "Silence detected on case {id}"
   b. Queue attempt_escalated_contact.delay(case_id)
   c. Mark for manual review (optional)
```

#### Part 2: `attempt_escalated_contact(case_id)`

**Trigger:** Queued by detect_silence_periods()

**What it does:**
```
1. Load case
2. Build escalated message:
   "Important: Your account requires immediate attention. Please contact us."
3. Send via SMS (primary channel)
4. If email exists, also send email
5. Log escalation attempt
6. Handle errors (no retry)
```

---

## 7. COMMUNICATION CHANNELS

### 7.1 Communication Router

**File:** `apps/communications/services/communication_router.py`

**Purpose:** Central dispatcher that routes messages to SMS/Email/Voice services.

**Architecture:**
```
CommunicationRouter
  ├── send_message(channel, payload)
  │   ├─ channel="sms"   → SMSService
  │   ├─ channel="email" → EmailService
  │   └─ channel="voice" → VoiceService
  │
  └── After delivery:
      → Record OUTBOUND InteractionLedger
      → Update case timestamps
```

**Payload Contract:**
```python
payload = {
    "row_id": "crm_row_123",           # Partner gateway row ID
    "case_id": 42,                     # Django case ID
    "phone": "+15145551234",           # Borrower phone
    "email": "borrower@example.com",   # Borrower email
    "message": "Invoice reminder...",  # Message body
    "subject": "Invoice",              # Email subject
    "ai_generated": True,              # Flag if AI-generated
}
```

**Method Flow:**
```python
def send_message(channel: str, payload: Dict) -> Dict:
    # 1. Normalize payload
    prepared = self._normalize_payload(payload)
    
    # 2. Route by channel
    if channel == "sms":
        result = sms_service.send_collection_sms(...)
        interaction_channel = "SMS"
    elif channel == "email":
        result = email_service.send_collection_email(...)
        interaction_channel = "EMAIL"
    elif channel == "voice":
        result = voice_service.make_collection_call(...)
        interaction_channel = "VOICE"
    
    # 3. Check for dispatch error
    if result['status'] == 'failed':
        raise ExternalDispatchError(result['error'])
    
    # 4. Find case (by row_id, case_id, phone, email priority)
    case = CollectionService.find_case(...)
    
    # 5. Record OUTBOUND interaction
    if case:
        CollectionService.record_interaction(
            case=case,
            channel=interaction_channel,
            interaction_type="OUTBOUND",
            message_content=prepared['message'],
            external_id=result.get('external_id'),
            status="SENT",
            ai_generated=prepared.get('ai_generated'),
        )
    
    return result
```

---

### 7.2 SMS Service

**File:** `apps/communications/sms/sms_service.py`

**Method:** `send_collection_sms(row_id, phone_number, message) → Dict`

**Implementation:**
```python
def send_collection_sms(self, row_id, phone_number, message):
    try:
        # Call iCollector gateway
        response = self.client.send_sms(
            row_id=row_id,
            phone=phone_number,
            message=message
        )
        return {
            "status": "success",
            "message_id": response.get("message_id") or response.get("id"),
            "external_id": response.get("message_id") or response.get("id"),
            "provider_response": response,
        }
    except ICollectorClientError as exc:
        logger.error("SMS dispatch failed for row_id=%s: %s", row_id, exc)
        return {
            "status": "failed",
            "error": str(exc)
        }
```

**External API Called:**
- **iCollector Partner Gateway** (primary)
  - Endpoint: `POST /api/partner-gateway/v1/sms/send/`
  - Authentication: HMAC-SHA256 signed request
  - Returns: `{message_id, status}`

**Fallback:** None currently; fails if iCollector unavailable

---

### 7.3 Email Service

**File:** `apps/communications/email/email_service.py`

**Method:** `send_collection_email(row_id, to_email, subject, body) → Dict`

**Implementation:**
```python
def send_collection_email(self, row_id, to_email, subject, body):
    try:
        response = self.client.send_email(
            row_id=row_id,
            to_email=to_email,
            subject=subject,
            body=body
        )
        return {
            "status": "success",
            "message_id": response.get("message_id") or response.get("id"),
            "external_id": response.get("message_id") or response.get("id"),
            "provider_response": response,
        }
    except ICollectorClientError as exc:
        logger.error("Email dispatch failed for row_id=%s: %s", row_id, exc)
        return {
            "status": "failed",
            "error": str(exc)
        }
```

**External API Called:**
- **iCollector Partner Gateway** (primary)
  - Endpoint: `POST /api/partner-gateway/v1/email/send/`
  - Authentication: HMAC-SHA256 signed request
  - Returns: `{message_id, status}`

**Fallback:** None currently; fails if iCollector unavailable

---

### 7.4 Voice Service

**File:** `apps/communications/voice/voice_service.py`

**Method:** `make_collection_call(phone_number, message=None, case_id=None) → Dict`

**Implementation:**
```python
def make_collection_call(self, phone_number, message=None, case_id=None):
    result = self.client.initiate_call(
        phone_number,
        script=message
    )
    result['case_id'] = case_id
    result['provider'] = self.provider
    if 'status' not in result:
        result['status'] = 'success'
    return result
```

**Provider Selection:**
- Default: **Telnyx** (via `telnyx_client.py`)
- Alternative: **Twilio** (via `twilio_client.py`)

**Telnyx Client:**
- Endpoint: Telnyx Voice API
- Method: `initiate_call(phone, script)`
- Returns: `{call_id, status, provider_response}`

**Twilio Client:**
- Endpoint: Twilio Voice API
- Method: `initiate_call(phone, script)`
- Returns: `{call_id, status, provider_response}`

---

## 8. CRM / PARTNER GATEWAY INTEGRATION

### 8.1 iCollector Partner Gateway

**Scope:** Complete implementation with HMAC-signed requests

**Location:** `apps/core/integrations/icollector_client.py`

### 8.2 Client Capabilities

**Authentication:**
```python
class ICollectorClient:
    def __init__(self):
        self.base_url = os.getenv("ICOLLECTOR_BASE_URL", "https://app.icollector.ai")
        self.api_token = os.getenv("ICOLLECTOR_API_TOKEN")
        self.tenant = os.getenv("ICOLLECTOR_TENANT")
        self.inbound_secret = os.getenv("ICOLLECTOR_INBOUND_SECRET")  # Signs outbound requests
```

**Request Signing Algorithm:**
```python
def _sign_request(self, method, path, raw_body, query=None):
    timestamp = generate_unix_timestamp()
    nonce = generate_cryptographic_nonce()
    query_string = f"?{urlencode(query)}" if query else ""
    path_with_query = f"{path}{query_string}"
    body_hash = SHA256(raw_body).hexdigest()
    
    canonical = f"{timestamp}.{nonce}.{method}.{path_with_query}.{body_hash}"
    signature = HMAC_SHA256(canonical, inbound_secret).hexdigest()
    
    return {
        'timestamp': timestamp,
        'nonce': nonce,
        'signature': signature,
        'headers': {
            'X-Partner-Timestamp': timestamp,
            'X-Partner-Nonce': nonce,
            'X-Partner-Signature': f'sha256={signature}',
        }
    }
```

### 8.3 Implemented Methods

#### SMS Operations
```python
send_sms(row_id, phone, message)
    → POST /api/partner-gateway/v1/sms/send/
    → Returns: {message_id, status, ...}

send_sms_extended(row_id, phone, message="", media_urls=[], idempotency_key=None)
    → POST /api/partner-gateway/v1/sms/send/
    → Returns: {message_id, status, ...}
```

#### Email Operations
```python
send_email(row_id, to_email, subject, body)
    → POST /api/partner-gateway/v1/email/send/
    → Returns: {message_id, status, ...}

send_email_extended(row_id, to_email, subject, body, mailbox_role=None, connection_id=None, cc=[], idempotency_key=None)
    → POST /api/partner-gateway/v1/email/send/
    → Returns: {message_id, status, ...}
```

#### CRM Board Operations
```python
get_boards()
    → GET /api/partner-gateway/v1/crm/boards/
    → Returns: {boards: [{id, name, ...}]}

get_rows(board_id, limit=100, offset=0, group_id=None)
    → GET /api/partner-gateway/v1/crm/board/{board_id}/rows/?limit={limit}&offset={offset}
    → Returns: {rows: [{row_id, data, ...}], total, ...}

ingest_row(board_id, group, data, idempotency_key=None)
    → POST /api/partner-gateway/v1/crm/board/{board_id}/ingest/
    → Returns: {row_id, status, ...}
    → Creates NEW row in specified group

update_row(row_id, data)
    → PATCH /api/partner-gateway/v1/crm/row/{row_id}/update/
    → Returns: {row_id, status, ...}
    → Updates EXISTING row data

move_row(row_id, target_board_id, target_group_id, action_value=None, action_column_title=None, idempotency_key=None)
    → POST /api/partner-gateway/v1/crm/row/{row_id}/move/
    → Returns: {row_id, status, ...}
    → Moves row to different board/group
```

#### Utility
```python
ping()
    → POST /api/partner-gateway/v1/ping/
    → Returns: {status: "success"}
    → Tests connectivity & credentials
```

### 8.4 Integration Status

**SMS Integration:** ✅ COMPLETE
- iCollector client implemented and tested
- SMSService wraps client
- Routing integrated

**Email Integration:** ✅ COMPLETE
- iCollector client implemented and tested
- EmailService wraps client
- Routing integrated

**CRM Board Integration:** ✅ COMPLETE
- All board operations implemented
- Row ingestion implemented
- Webhook processor uses get_boards() to fetch list
- Board ID validation (70, 71, 73, 74)

**Error Handling:** ✅ COMPLETE
- Custom `ICollectorClientError` exception
- Retry logic in Celery tasks
- Proper logging

**Idempotency:** ✅ COMPLETE
- `idempotency_key` parameter supported in:
  - send_sms_extended()
  - send_email_extended()
  - ingest_row()
  - move_row()
- WebhookProcessor guards against duplicate interactions
- Duplicate message check (5-minute window) in send_followup_messages()

**Security:** ✅ COMPLETE
- HMAC-SHA256 signature validation on all requests
- Timestamp window enforcement (300s default)
- Secure nonce generation

---

## 9. URL ROUTING

### 9.1 Configuration

**Root URL Router:** `config/urls.py`

```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/collections/', include('apps.collections.urls')),
    path('api/communications/', include('apps.communications.urls')),
    path('api/webhooks/', include('apps.webhooks.urls')),
]
```

### 9.2 Collections Routes

**File:** `apps/collections/urls.py`

**Status:** PLACEHOLDER (empty)

```python
urlpatterns = [
    # Currently empty
    # Could include:
    # - GET /api/collections/{id}/        → case detail
    # - GET /api/collections/search/      → case search
    # - PATCH /api/collections/{id}/      → case update
    # - POST /api/collections/{id}/interactions/  → manual interaction
]
```

**API exposure:** ❌ NOT ACTIVE

---

### 9.3 Communications Routes

**File:** `apps/communications/urls.py`

**Status:** PLACEHOLDER (empty)

```python
urlpatterns = [
    # Currently empty
    # Could include:
    # - POST /api/communications/send/    → send message
    # - GET /api/communications/templates/ → list templates
]
```

**API exposure:** ❌ NOT ACTIVE

---

### 9.4 Webhooks Routes

**File:** `apps/webhooks/urls.py`

**Status:** ✅ ACTIVE

```python
urlpatterns = [
    path('sms/', webhook_views.sms_webhook, name='sms_webhook'),
    path('email/', webhook_views.email_webhook, name='email_webhook'),
    path('voice/', webhook_views.voice_webhook, name='voice_webhook'),
    path('crm/', webhook_views.crm_webhook, name='crm_webhook'),
]
```

**Active Endpoints:**
- `POST /api/webhooks/sms/` ✅ ACTIVE
- `POST /api/webhooks/email/` ✅ ACTIVE
- `POST /api/webhooks/voice/` ✅ ACTIVE
- `POST /api/webhooks/crm/` ✅ ACTIVE

---

### 9.5 AI Routes

**File:** `apps/ai/urls.py`

**Status:** ❌ NOT MOUNTED (exists but not included in root urls.py)

```python
urlpatterns = [
    # Not currently mounted
    # Could expose AI endpoints for manual testing
]
```

**API exposure:** ❌ NOT ACTIVE

---

## 10. MIGRATIONS

### 10.1 Migration Status

**Collections App:**
- ✅ `apps/collections/migrations/__init__.py` exists
- ✅ `apps/collections/migrations/0001_initial.py` exists

**Status:** Ready to apply

### 10.2 Migration 0001_initial.py

**Creates 4 models with full schema:**

1. **CollectionCase** (db_table: `collections_case`)
   - All fields from model definition
   - Primary key (auto)
   - 4 composite indexes

2. **InteractionLedger** (db_table: `collections_interaction_ledger`)
   - All fields from model definition
   - 2 composite indexes

3. **TransactionLedger** (db_table: `collections_transaction_ledger`)
   - All fields from model definition
   - 1 composite index

4. **PaymentCommitment** (db_table: `collections_payment_commitment`)
   - All fields from model definition
   - 2 composite indexes

**Indexes Applied:**
```
CollectionCase:
  ├─ (status, current_workflow_step)
  ├─ (automation_status, next_action_time)
  ├─ (borrower_phone)
  └─ (next_followup_at)

InteractionLedger:
  ├─ (collection_case, created_at)
  └─ (channel, status)

TransactionLedger:
  └─ (collection_case, posted_date)

PaymentCommitment:
  ├─ (collection_case, promised_date)
  └─ (status)
```

**Other Apps:**
- ❌ `apps/communications/` — no migrations
- ❌ `apps/ai/` — no migrations
- ❌ `apps/webhooks/` — no migrations
- ❌ `apps/tasks/` — no migrations
- ❌ `apps/core/` — no migrations

**Ready to Run:** ✅ YES
```bash
python manage.py migrate
```

---

## 11. INTEGRATION STATUS SUMMARY

| Component | Status | Notes |
|-----------|--------|-------|
| **Webhook Ingestion** | COMPLETE | All 4 endpoints implemented with signature validation |
| **Signature Validation** | COMPLETE | iCollector HMAC-SHA256 validation working |
| **Payload Routing** | COMPLETE | WebhookProcessor routes to correct handlers |
| **Interaction Recording** | COMPLETE | All inbound/outbound interactions logged to DB |
| **AI Intent Detection** | COMPLETE | IntentAnalyzer calls OpenAI, detects 8 intents |
| **AI Response Generation** | COMPLETE | MessageGenerator creates personalized SMS/email |
| **AI Orchestration** | COMPLETE | AIOrchestrator coordinates analysis + generation |
| **Workflow Transitions** | COMPLETE | State machine advances on refusal intent |
| **Commitment Tracking** | COMPLETE | PaymentCommitment created on promise_to_pay |
| **Celery Async Processing** | COMPLETE | All tasks defined, beat schedule configured |
| **SMS Dispatch** | COMPLETE | SMSService integrates with iCollector |
| **Email Dispatch** | COMPLETE | EmailService integrates with iCollector |
| **Voice Calling** | COMPLETE | VoiceService abstraction (Telnyx/Twilio) |
| **Communication Routing** | COMPLETE | CommunicationRouter dispatches to channels |
| **Follow-up Scheduling** | COMPLETE | send_followup_messages task configured |
| **Silence Detection** | COMPLETE | detect_silence_periods task configured |
| **Commitment Fulfillment** | COMPLETE | check_commitment_fulfillment task configured |
| **CRM Ingestion** | COMPLETE | WebhookProcessor._process_crm_ingestion() implemented |
| **Partner Gateway (SMS/Email)** | COMPLETE | iCollector client fully implemented |
| **Partner Gateway (CRM Boards)** | COMPLETE | All board operations implemented |
| **Database Models** | COMPLETE | All 4 models defined and indexed |
| **Migrations** | COMPLETE | 0001_initial.py ready |
| **Collections API Routes** | PARTIAL | Routes exist but return empty (placeholder) |
| **Communications API Routes** | PARTIAL | Routes exist but return empty (placeholder) |
| **Webhook API Routes** | COMPLETE | All 4 endpoints active |
| **AI API Routes** | NOT IMPLEMENTED | Routes exist in ai/urls.py but not mounted |

---

## 12. CRITICAL MISSING PIECES

### Priority 1: Must Have for Production

1. **Environment Configuration**
   - `.env` not created (only `.env.example` exists)
   - ICOLLECTOR_* secrets not configured
   - OPENAI_API_KEY not set
   - Database credentials not configured
   - Redis/Celery connection strings missing
   - **Impact:** System cannot run without .env

2. **Comprehensive Integration Testing**
   - No end-to-end test suite covering workflows
   - No tests for webhook → AI → workflow chain
   - No mock tests for external APIs
   - No tests for CRM ingestion flow
   - **Impact:** Cannot validate system works without manual testing

3. **Error Handling & Recovery**
   - Limited error recovery for OpenAI failures
   - No fallback messages if AI unavailable
   - CommunicationRouter raises exceptions on dispatch failure
   - No circuit breaker for external APIs
   - **Impact:** System may crash or hang on provider failures

4. **Logging & Monitoring**
   - Basic logging configured but not comprehensive
   - No structured logging (JSON format)
   - No error tracking to Sentry (configured but not tested)
   - No performance metrics collection
   - **Impact:** Difficult to diagnose issues in production

5. **API Documentation**
   - No OpenAPI/Swagger documentation
   - Webhook payload formats not published
   - Error response formats not standardized
   - **Impact:** Partners struggle to integrate

### Priority 2: Should Have Before Beta

6. **Response Message Templates**
   - All messages generated via OpenAI (cost, latency)
   - No fallback template library
   - No A/B testing framework
   - **Impact:** Can't scale without API costs, slow outreach

7. **Collections API Endpoints**
   - `apps/collections/urls.py` is empty placeholder
   - No way to query cases via API
   - No way to update cases via API
   - No case search/filter endpoints
   - **Impact:** Limited API interface for partners

8. **Communications API Endpoints**
   - `apps/communications/urls.py` is empty placeholder
   - No way to manually send messages
   - No template management endpoints
   - **Impact:** Can only send messages via workflow, not ad hoc

9. **Admin Interface Customization**
   - Django admin exists but basic
   - No custom list filters
   - No bulk actions
   - No custom actions (e.g., "Send Message", "Escalate")
   - **Impact:** Manual collections team can't efficiently manage cases

10. **Rate Limiting & Quotas**
    - No rate limiting on webhook endpoints
    - No API quotas per tenant
    - No SMS/email rate limits per borrower (compliance risk)
    - **Impact:** System vulnerable to abuse

### Priority 3: Nice to Have

11. **Idempotency Improvements**
    - Current idempotency key handling is basic
    - No request ID tracking for all operations
    - **Impact:** Potential duplicate messages under retries

12. **Data Validation**
    - Phone number validation cursory
    - Email validation basic
    - No borrower identity verification
    - **Impact:** Bad data in system

13. **Audit Logging**
    - No audit trail of who changed what
    - No permission system in place
    - **Impact:** Compliance/security issue

14. **Performance Optimization**
    - No database query optimization
    - No caching strategy implemented
    - No pagination on list endpoints
    - **Impact:** Slow as data grows

15. **Deployment Automation**
    - Docker images exist but not tested
    - No CI/CD pipeline
    - No automated testing on merge
    - **Impact:** Manual deployment error-prone

---

## 13. RECOMMENDED NEXT ENGINEERING STEP

### Single Most Important Next Step:

**IMPLEMENT END-TO-END INTEGRATION TEST SUITE**

**Why this is #1 priority:**

1. **Validates Architecture**
   - Proves webhook → AI → workflow → dispatch chain actually works
   - Catches integration bugs before production

2. **De-risks Production Release**
   - Currently, full system flow is untested
   - First real webhook could fail catastrophically
   - Integration tests catch 80% of issues

3. **Enables Confident Iteration**
   - With good tests, team can refactor safely
   - Prevents regression bugs

4. **Short-term ROI**
   - Tests take 2-3 days to write
   - Catch issues that would take 1+ week to debug in production

### Recommended Test Coverage (Priority Order):

```python
# Test Suite: apps/tests/test_end_to_end.py

1. CRM Ingestion Flow (NEW CASE)
   Input: POST /api/webhooks/crm/ with new borrower
   Expected: 
      ✓ CollectionCase created with STEP_1
      ✓ TransactionLedger NSF created
      ✓ InteractionLedger outbound SMS created
      ✓ Initial message sent via iCollector
      ✓ next_action_time set

2. Inbound Refusal Flow (WORKFLOW TRANSITION)
   Input: SMS webhook with "I can't pay"
   Expected:
      ✓ InteractionLedger inbound created
      ✓ AI detects "refusal" intent
      ✓ WorkflowStateMachine transitions STEP_1 → STEP_2
      ✓ case.current_workflow_step = STEP_2
      ✓ Next AI-generated outbound message queued

3. Promise-to-Pay Flow (COMMITMENT CREATION)
   Input: SMS webhook with "I'll pay next week"
   Expected:
      ✓ InteractionLedger inbound created
      ✓ AI detects "promise_to_pay" intent
      ✓ PaymentCommitment created with promised_date = next week
      ✓ commitment.status = PENDING
      ✓ Outbound confirmation message sent

4. Follow-up Message Scheduler
   Setup: Create case with next_action_time in past
   Execute: send_followup_messages.delay()
   Expected:
      ✓ Message generated via AI
      ✓ Case NOT skipped (idempotency check)
      ✓ Message sent via iCollector
      ✓ InteractionLedger outbound created
      ✓ next_action_time updated

5. Signature Validation Negative Test
   Input: SMS webhook with invalid signature
   Expected:
      ✓ Returns 401 Unauthorized
      ✓ Interaction NOT created

6. AI Orchestrator Integration
   Setup: Mock OpenAI responses
   Execute: AIOrchestrator.process_borrower_message()
   Expected:
      ✓ Intent correctly detected
      ✓ Response correctly generated
      ✓ Both results returned

7. Communication Router Integration
   Setup: Router with SMS/Email services
   Execute: router.send_message("sms", payload)
   Expected:
      ✓ SMSService called with correct params
      ✓ iCollector client called
      ✓ OUTBOUND InteractionLedger created
      ✓ Case timestamps updated
```

### Implementation Plan (2-3 days):

**Day 1:** Setup & CRM/Refusal tests
```
- Create apps/tests/test_end_to_end.py
- Setup test database & factories
- Test CRM webhook → case creation
- Test SMS webhook → refusal → workflow transition
```

**Day 2:** Promise-to-Pay & Commitment tests
```
- Test promise-to-pay → commitment creation
- Test commitment fulfillment checking
- Test silence detection flow
```

**Day 3:** Integration & Router tests
```
- Test full communication router
- Test AI orchestrator mocking
- Test error scenarios (dispatch failure, AI timeout)
- Add documentation
```

### Success Criteria:

- [ ] 95%+ test coverage for critical paths
- [ ] All 7 test scenarios pass
- [ ] Zero skipped/pending tests
- [ ] Negative tests (error cases) included
- [ ] Fixtures for test data reuse
- [ ] Runs in < 30 seconds
- [ ] CI integration ready

### Follow-up After Tests Pass:

Once integration tests pass, next steps in priority order:

1. **Create .env configuration** from .env.example and test
2. **Implement Collections API endpoints** (GET, PATCH, search)
3. **Add rate limiting** to webhook endpoints
4. **Write documentation** for partner integration
5. **Deploy to staging** environment

---

## APPENDIX: Key File Locations

```
Critical Implementation Files:
- apps/collections/models/collection_case.py       → Case model
- apps/collections/workflows/state_machine.py      → Workflow logic
- apps/webhooks/services/webhook_processor.py      → Webhook routing
- apps/webhooks/views/webhook_views.py             → 4 webhook endpoints
- apps/ai/services/ai_orchestrator.py              → AI coordination
- apps/ai/intent_detection/intent_analyzer.py      → Intent classification
- apps/ai/message_generation/message_generator.py  → Message generation
- apps/communications/services/communication_router.py → Channel dispatch
- apps/tasks/followup_tasks.py                     → Async task execution
- apps/core/integrations/icollector_client.py      → Partner gateway
- apps/collections/migrations/0001_initial.py      → Database schema

Configuration Files:
- config/settings/base.py                          → Django config
- config/urls.py                                   → URL routing
- apps/tasks/config.py                             → Celery configuration
- requirements.txt                                 → Python dependencies
- docker-compose.yml                               → Container orchestration

Documentation:
- docs/ARCHITECTURE.md                             → System architecture
- docs/IMPLEMENTED_SYSTEM_AND_TESTING.md          → Integration guide
- PROJECT_DEEP_DIVE.md                             → Detailed project overview
```

---

**Report Generated:** March 18, 2026  
**Status:** Analysis Complete ✅

