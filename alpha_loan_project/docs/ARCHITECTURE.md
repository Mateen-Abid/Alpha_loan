"""Architecture Overview - Alpha Loan Collections Platform

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    External Systems                         │
├──────────────────────┬──────────────┬──────────────────────┤
│   Heymarket (SMS)   │  Gmail/Email │ Telnyx/Twilio (Voice)│
│        CRM           │   System      │   Payment Gateway   │
└──────────────────────┴──────────────┴──────────────────────┘
                        ↓         ↓         ↓
┌─────────────────────────────────────────────────────────────┐
│              Webhook Layer (apps/webhooks)                  │
├──────────────────┬──────────────┬──────────────────────────┤
│  SMS Handlers    │ Email Handler│  Voice Handler / CRM     │
│ - Signature Validate              Handlers                 │
│ - Payload Validate   - Process                              │
│ - Route to Service   - Engage AI                            │
└──────────────────┴──────────────┴──────────────────────────┘
                    ↓         ↓
┌─────────────────────────────────────────────────────────────┐
│         Task Queue (Celery + Redis)                        │
├──────────────────────────────────────────────────────────────┤
│ - Process AI Analysis                                       │
│ - Record Interactions                                       │
│ - Queue Follow-up Messages                                  │
│ - Check Commitments                                         │
│ - Detect Silence                                            │
└──────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            AI Processing Layer (apps/ai)                    │
├──────────────────┬──────────────────┬──────────────────────┤
│ Intent Detection │ Message Generation│   AI Orchestrator   │
│ - Classify text  │ - Generate SMS   │ - Coordinate ops    │
│ - Extract intent │ - Generate Email │ - Stateless         │
│ - Sentiment      │ - Personalize    │                      │
└──────────────────┴──────────────────┴──────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│    Communications Layer (apps/communications)               │
├────────────────┬──────────────┬───────────────────────────┤
│  SMS Service   │ Email Service│   Voice Service           │
│ - Heymarket    │ - Gmail      │ - Telnyx/Twilio         │
│   Client       │   Client     │   Client                 │
└────────────────┴──────────────┴───────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│     Collections Layer (apps/collections)                    │
├──────────────────┬──────────────┬──────────────────────────┤
│ Collection Logic │ Workflow SM  │ Services  │ Repositories │
│ - Cases          │ - State      │ - Biz     │ - Data       │
│ - Transactions   │   Management │   Logic   │   Access     │
│ - Interactions   │ - Transition │           │              │
│ - Commitments    │   Logic      │           │              │
└──────────────────┴──────────────┴──────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────────┐
│              Database Layer (PostgreSQL)                    │
├──────────────┬──────────────┬──────────────┬───────────────┤
│ CollectionCase│ Transaction   │ Interaction  │ Payment       │
│              │ Ledger        │ Ledger       │ Commitment    │
└──────────────┴──────────────┴──────────────┴───────────────┘
```

## Data Flow - Incoming SMS Reply

```
1. Borrower sends SMS
   ↓
2. Heymarket receives SMS
   ↓
3. Heymarket sends webhook to /api/webhooks/sms/
   ↓
4. SMS Webhook Handler
   - Validates signature
   - Validates payload
   - Records InteractionLedger entry
   ↓
5. Queue to Celery: process_borrowed_message task
   ↓
6. AI Processing (Celery Worker)
   - Intent Analyzer: Detect intent
   - Update InteractionLedger with intent
   ↓
7. Workflow Processing
   - If intent == "refusal": advance workflow step
   - If intent == "promise_to_pay": create PaymentCommitment
   - Record transaction if payment mentioned
   ↓
8. Optional: Queue response message
   - Message Generator: Create response
   - Communication Router: Send response via SMS
```

## Data Flow - Outbound Collection Message

```
1. CollectionCase needs follow-up
   ↓
2. Scheduled task: send_followup_messages()
   ↓
3. CollectionService
   - Get active cases needing follow-up
   - For each case:
   ↓
4. AI Generation (optional)
   - AIOrchestrator.generate_outbound_message()
   - Message Generator creates personalized message
   ↓
5. Communication Router
   - Route to SMS, Email, or Voice service
   - SMSService.send_collection_sms()
   ↓
6. External API
   - Heymarket, Gmail, Telnyx
   - Send message to borrower
   ↓
7. Record Interaction
   - Create InteractionLedger entry
   - Set status: SENT
   - Store external_id from provider
   ↓
8. Await Webhook
   - Wait for delivery/read/reply webhook
   - Update InteractionLedger status
```

## Workflow State Machine

```
                    ┌─────────────────┐
                    │     STEP_1      │
                    │ Immediate Pay   │
                    └────────┬────────┘
                             │
                    Borrower Refuses
                             │
                             ↓
                    ┌─────────────────┐
                    │     STEP_2      │
                    │ Double Payment  │
                    └────────┬────────┘
                             │
                    Borrower Refuses
                             │
                             ↓
                    ┌─────────────────┐
                    │     STEP_3      │
                    │  Add NSF Fee    │
                    └────────┬────────┘
                             │
                    Borrower Refuses
                             │
                             ↓
                    ┌─────────────────┐
                    │     STEP_4      │
                    │  Split Payment  │
                    └────────┬────────┘
                             │
                    Borrower Refuses
                             │
                             ↓
                    ┌─────────────────┐
                    │ FINAL_PRESSURE  │
                    │  Final Notice   │
                    └─────────────────┘

States are advanced ONLY when:
- Borrower explicitly refuses to pay
- Payment commitment is broken
- Other escalation events occur

Workflow is deterministic in backend:
- AI can analyze messages
- AI can generate suggestions
- But workflow logic stays in WorkflowStateMachine
```

## API Integration Points

### Inbound (Webhooks)

**SMS Webhook** (Heymarket)
- URL: POST `/api/webhooks/sms/`
- Auth: HMAC-SHA256 signature validation
- Body: `{from, message, message_id, timestamp}`

**Email Webhook** (Gmail/Custom)
- URL: POST `/api/webhooks/email/`
- Auth: Custom header validation
- Body: `{from, to, subject, body, message_id}`

**Voice Webhook** (Telnyx/Twilio)
- URL: POST `/api/webhooks/voice/`
- Auth: Provider-specific signature
- Body: `{call_id, to, duration, transcript, status}`

**CRM Webhook** (Payment/Account Updates)
- URL: POST `/api/webhooks/crm/`
- Auth: API key header
- Body: `{event_type, account_id, ...}`

### Outbound (API Calls)

**SMS Send** (Heymarket API)
- Endpoint: `POST /v1/messages`
- Auth: Bearer token
- Returns: `{message_id, status}`

**Email Send** (Gmail API)
- Endpoint: `POST /gmail/v1/users/me/messages/send`
- Auth: OAuth 2.0
- Returns: `{id, status}`

**Voice Call** (Telnyx API)
- Endpoint: `POST /v2/calls`
- Auth: Bearer token
- Returns: `{call_id, status}`

**AI Processing** (OpenAI API)
- Endpoint: `POST /v1/chat/completions`
- Auth: API key
- Returns: `{choices: [{message: {content}}]}`

## Database Schema

### Collections Models

**CollectionCase**
- account_id: unique identifier
- borrower info: name, email, phone
- amount info: principal, total_due, amount_paid
- workflow: current_step, step_started_at
- status: ACTIVE, RESOLVED, LOST, SUSPENDED
- timestamps: created_at, updated_at

**TransactionLedger** (audit trail)
- collection_case_id: FK
- type: PAYMENT, ADJUSTMENT, FEE, NSF, REVERSAL
- amount, date, description
- external_reference: payment gateway ID

**InteractionLedger** (communication log)
- collection_case_id: FK
- channel: SMS, EMAIL, VOICE
- direction: OUTBOUND, INBOUND
- message content
- status: PENDING, SENT, DELIVERED, READ, REPLIED, FAILED
- AI analysis: intent, sentiment_score
- external_id: Heymarket ID, Gmail message ID, etc.

**PaymentCommitment** (promise-to-pay)
- collection_case_id: FK
- committed_amount, amount_paid
- promised_date
- status: PENDING, CONFIRMED, FULFILLED, BROKEN
- payment_method, source

## Deployment Architecture

```
┌─────────────────────────────────────────────┐
│         Load Balancer (Nginx)               │
│         (SSL Termination)                   │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ↓          ↓          ↓
┌──────────────┐
│ Django Web   │  (Multiple instances)
│ (Gunicorn)   │
└──────────────┘
        ↓
┌───────────────────┐
│ PostgreSQL (Main) │
│ + Read Replicas   │
└───────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Celery Work. │  │ Celery Work. │  │ Celery Work. │
│ (Multiple)   │  │ (Multiple)   │  │ (Multiple)   │
└──────────────┘  └──────────────┘  └──────────────┘
        ↓                 ↓                  ↓
┌────────────────────────────────────────────────────┐
│              Redis Cluster                        │
│         (Broker + Cache) HA Setup                  │
└────────────────────────────────────────────────────┘

┌──────────────────────┐
│  Celery Beat         │
│  (Scheduler)         │
└──────────────────────┘

┌──────────────────────┐
│  Monitoring Stack    │
│  - Prometheus        │
│  - Grafana           │
│  - Sentry (Errors)   │
└──────────────────────┘
```

## Key Design Patterns

1. **Service Layer**: Business logic separated from models
   - CollectionService, SMSService, EmailService, etc.

2. **Repository Pattern**: Data access abstraction
   - CollectionCaseRepository, etc.

3. **State Machine**: Deterministic workflow control
   - WorkflowStateMachine with explicit state transitions

4. **Webhook Handler Pattern**: Async processing
   - Handlers validate → Queue to Celery → Process asynchronously

5. **Service Locator**: Channel selection
   - CommunicationRouter routes to appropriate service

6. **Factory Pattern**: Dynamic client instantiation
   - SMSService creates HeymarketClient, etc.

## Security Considerations

1. **Webhook Validation**: All webhooks validated by signature
2. **API Keys**: Environment variables only
3. **Encryption**: Sensitive data encrypted at rest
4. **HTTPS**: Required in production
5. **CORS**: Properly configured
6. **Rate Limiting**: Can be added at API layer
7. **Authentication**: Token or session-based
8. **Input Validation**: All webhook payloads validated

## Performance Optimization

1. **Database**: PostgreSQL with proper indexing
2. **Cache**: Redis for session and result caching
3. **Async**: Celery for non-blocking operations
4. **Pagination**: REST API with pagination
5. **Query Optimization**: Select_related, prefetch_related
6. **Rate Limiting**: Prevent API abuse

## Error Handling & Monitoring

1. **Logging**: Structured logging to files and centralized system
2. **Error Tracking**: Sentry for exception monitoring
3. **Metrics**: Prometheus for application metrics
4. **Health Checks**: Periodic health checks for services
5. **Alerts**: PagerDuty or similar for critical issues
6. **Audit Trail**: All actions logged in database

"""
