# Testing Procedure for Alpha Loans Collections Platform

Based on both the Collections Platform specification and iCollectorAI Partner Gateway Integration Handbook.

---

## Testing Overview

**Total: 160 test cases across 8 phases = ~15 days of testing**  
**Estimated Timeline:** 3 weeks with parallel testing, 1 week sequential

---

## **PHASE 1: PARTNER GATEWAY CONNECTIVITY** (Days 1-2)

### Steps 1-5: Authentication & Signing

**1. Setup environment**
- Store API key, tenant slug, inbound/outbound secrets
- Create `.env` with PARTNER_API_KEY, TENANT_SLUG, INBOUND_SECRET, OUTBOUND_SECRET

**2. Test ping endpoint**
- Call `POST /api/partner-gateway/v1/ping/`
- Verify valid HMAC signature works
- Expected: `{"status": "ok", "tenant_slug": "...", "gateway_active": true}`

**3. Test invalid signature**
- Modify signature header intentionally
- Call ping endpoint
- Expected: `401 Unauthorized` with code `invalid_signature`

**4. Test replay detection**
- Send same request with same nonce twice
- Expected: First succeeds, second returns `409 Conflict` with code `replay_detected`

**5. Test timestamp window**
- Send request with timestamp 400 seconds in past (window is 300s)
- Expected: `401 Unauthorized` with code `timestamp_out_of_window`

**Success criteria:** Signatures verified, 401/409 responses correct

---

### Steps 6-10: CRM Discovery

**6. Get boards list**
- Call `GET /api/partner-gateway/v1/crm/boards/`
- Expected: All 4 accessible boards returned (70, 71, 73, 74)

**7. Validate board names**
- Confirm:
  - Board 70: "Daily Rejects"
  - Board 71: "E-Transfer"
  - Board 73: "E-Transfer Agreements"
  - Board 74: "Received E-Transfer"

**8. Get board rows**
- Call `GET /api/partner-gateway/v1/crm/board/70/rows/?limit=100&offset=0`
- Expected: Rows returned with all columns

**9. Test limit/offset**
- Call with `limit=10&offset=0`, then `limit=10&offset=10`
- Confirm pagination works correctly
- Total count matches across requests

**10. Inspect row structure**
- Verify columns include:
  - `Client` (text)
  - `Phone Number` (text)
  - `Email` (email)
  - `Action` (status with labels)
  - `Frequency` (status with labels)

**Success criteria:** All 4 boards returned, pagination works, row data complete

---

## **PHASE 2: CRM OPERATIONS** (Days 3-4)

### Steps 11-15: Safe Mutations

**11. Update non-critical column**
- Call `PATCH /api/partner-gateway/v1/crm/row/{test_row_id}/update/`
- Update `Client` name from "John Doe" to "Jane Doe"
- Expected: `{"status": "updated", "updated_cells": 1}`

**12. Verify idempotency**
- Resend same update with same `idempotency_key`
- Expected: Response includes `idempotent_replay=true`
- Data unchanged (only one update occurs)

**13. Update Action column**
- Set Action to `{"label": "Etransfer"}`
- Expected: Update succeeds, status updated

**14. Update Frequency column**
- Set Frequency to `{"label": "1 payment"}`
- Expected: Update succeeds, status updated

**15. Verify automation trigger**
- Confirm columns updated in iCollectorAI system
- Check iCollectorAI logs show update occurred
- Verify existing automations triggered (if configured for these conditions)

**Success criteria:** Updates persisted, idempotency works, no errors

---

### Steps 16-20: Row Lifecycle

**16. Ingest new row**
- Call `POST /api/partner-gateway/v1/crm/board/70/ingest/`
- Create test row with:
  - `Client`: "Test Borrower"
  - `Phone Number`: "+15145551111"
  - `Email`: "test@example.com"
  - `Action`: "Review"
- Expected: `{"status": "created", "row": {"id": <new_id>}}`

**17. Verify row created**
- Confirm row_id returned
- Query rows again, verify new row appears in list
- Confirm row in board 70, group 91

**18. Move row**
- Call `POST /api/partner-gateway/v1/crm/row/{new_row_id}/move/`
- Move from board 70 to board 71
- Specify `target_group_id: 93` (Overdue group)
- Expected: `{"status": "moved", "row": {"id": <id>, "board": 71, "group": 93}}`

**19. Verify move successful**
- Query board 71 rows, confirm row appears there
- Query board 70 rows, confirm row no longer there
- Confirm row in correct group (93)

**20. Validate automation compatibility**
- Trigger existing Daily→E-Transfer automation
- Confirm automation decision-making works with partner-created rows

**Success criteria:** Row created/moved successfully, automation paths work

---

## **PHASE 3: COMMUNICATION CHANNELS** (Days 5-6)

### Steps 21-25: SMS Integration

**21. Send test SMS**
- Call `POST /api/partner-gateway/v1/sms/send/`
- Send to controlled test number (company phone: +15145551111)
- Message: "Test SMS from iCollectorAI partners"
- Expected: `{"status": "sent", "sms_log": {...}, "provider_result": {...}}`

**22. Capture message_id**
- Verify response includes `message_id`
- Verify response includes `provider_result` with provider-specific ID

**23. Verify SMS log**
- Confirm SMS appears in iCollectorAI SMS logs
- Check log shows:
  - row_id
  - phone
  - status: "sent"
  - provider status

**24. Test with media_urls**
- Send SMS with document attachment
- Include `media_urls: ["https://files.example.com/doc.pdf"]`
- Expected: SMS sent with media attached

**25. Verify media attachment**
- Confirm attachment delivered to recipient
- Check provider logs show media transmitted

**Success criteria:** SMS sent, logged, message tracked, media delivered

---

### Steps 26-30: Email Integration

**26. Send test email**
- Call `POST /api/partner-gateway/v1/email/send/`
- Send to controlled test inbox (company email)
- Subject: "Test Email from iCollectorAI"
- Body: "This is a test email"
- Expected: `{"status": "sent", "email_log": {...}}`

**27. Capture email_log_id**
- Verify response includes email log ID
- Verify response includes sender mailbox info

**28. Test mailbox_role**
- Send using `"mailbox_role": "primary"`
- Expected: Email sent from primary mailbox

**29. Test explicit connection_id**
- Send using `"connection_id": 42` (explicit mailbox)
- Expected: Email sent from specified connection

**30. Verify email log**
- Confirm email appears in iCollectorAI email logs
- Check log shows:
  - row_id
  - to_email
  - status: "sent"
  - mailbox used

**Success criteria:** Email sent, logged, delivery tracked, correct mailbox used

---

## **PHASE 4: COLLECTIONS WORKFLOW SIMULATION** (Days 7-9)

### Steps 31-40: STEP_1 (Immediate Payment)

**31. Create new CollectionCase**
- Simulate CRM webhook with NSF return reason:
  - `row_id`: 12001
  - `board_id`: 70
  - `phone`: "+15145551234"
  - `email`: "borrower@example.com"
  - `failed_payment_amount`: 146.25
  - `return_reason`: "nsf"
- Expected: CollectionCase created in database

**32. Verify case created**
- Query: `CollectionCase.objects.get(partner_row_id=12001)`
- Verify:
  - status = ACTIVE
  - current_workflow_step = STEP_1
  - automation_status = ACTIVE
  - total_due = 146.25

**33. Verify transaction recorded**
- Query: `TransactionLedger.objects.filter(collection_case=case, transaction_type='NSF')`
- Verify:
  - amount = 50.00 (NSF fee)
  - description mentions NSF
  - posted_date = today

**34. Verify initial message queued**
- Query: `InteractionLedger.objects.filter(collection_case=case, interaction_type='OUTBOUND')`
- Verify outbound SMS created
- Check message_content

**35. Confirm payment amount**
- Verify message shows: "$196.25" ($146.25 + $50 NSF fee)
- Tone should be: "courteous and professional" (STEP_1 tone)

**36. Send refusal response**
- Simulate SMS webhook: borrower replies "I can't pay that"
- POST: `/api/webhooks/sms/` with signature
- Payload:
  - `phone`: "+15145551234"
  - `message`: "I can't pay that"
  - `message_id`: "hm_001"

**37. Verify AI intent detection**
- Query: `InteractionLedger.objects.filter(collection_case=case, interaction_type='INBOUND')`
- Verify inbound interaction created
- Check: `ai_intent_detected = "refusal"`
- Check: `ai_sentiment_score` reflects negative tone

**38. Verify workflow advance**
- Query case again
- Verify: `current_workflow_step = STEP_2`
- Verify: `workflow_step_started_at` updated to current time

**39. Verify new message generated**
- Query newest outbound message
- Check tone: "urgent but professional" (STEP_2 tone)
- Check amount: "$292.50" (double payment)

**40. Verify next_action_time updated**
- Check: `case.next_action_time` is set
- Check: `case.next_followup_at` is set
- Both should be ~24 hours in future

**Success criteria:** Full workflow loop executes, phase advances on refusal

---

### Steps 41-50: STEP_2 (Double Payment)

**41. Receive STEP_2 message**
- Confirm outbound SMS contains "Double Payment" option
- Parse amount: $292.50
- Tone: urgent, professional

**42. Send agreement response**
- Simulate SMS webhook: borrower replies "OK, I'll do that"
- Payload: `message: "OK, I'll do that"`
- POST: `/api/webhooks/sms/`

**43. Verify AI intent detection**
- Query new inbound interaction
- Verify: `ai_intent_detected = "promise_to_pay"`
- Verify: `ai_sentiment_score` positive

**44. Verify PaymentCommitment created**
- Query: `PaymentCommitment.objects.get(collection_case=case)`
- Verify exists (previously should be none)
- Verify `amount = 292.50`

**45. Verify promised_date set**
- Check: `promised_date = today + 3 days`
- Represents next regular payment cycle

**46. Verify commitment_status = PENDING**
- Check: `status = "PENDING"`
- Check: `created_at = now`

**47. Verify outbound confirmation**
- Query newest outbound message
- Verify confirmation message sent
- Verify mentions commitment amount and date

**48. Simulate payment on promised_date**
- Advance system time to promised_date
- Simulate payment received via CRM webhook:
  - `payment_amount`: 292.50
  - `return_reason`: null (success)

**49. Verify commitment fulfilled**
- Query commitment
- Verify: `status = "FULFILLED"`
- Verify: `amount_paid = 292.50`

**50. Verify case status**
- Query case
- Verify: `status = "RESOLVED"`
- Verify: `automation_status = "STOPPED"` or equivalent

**Success criteria:** Full promise-to-pay cycle works, commitment tracked, case resolved

---

### Steps 51-60: Silence Follow-Up (STEP_1 with no reply)

**51. Create case in STEP_1**
- New NSF ingestion, case in STEP_1
- Verify initial message sent

**52. Send initial message**
- Confirm payment demand sent
- Message contains amount and payment instructions

**53. Set 60-minute timer**
- Simulate no response from borrower
- Time advances 60 minutes
- No SMS/email received

**54. Trigger silence task**
- Execute: `Celery detect_silence_periods()` check at 6-hour mark
- Actually advance time to trigger scheduler

**55. Verify randomized follow-up queued**
- Query outbound interactions
- Should have 2+ messages
- Message 2 should differ from Message 1

**56. Confirm wording variation**
- Messages should not be identical
- Example variations:
  - "Your returned payment remains unresolved."
  - "Please reply so we can resolve this today."
  - "We still need payment of $196.25"

**57. Check friction counter**
- Verify: `message_friction_count = 0`
- Silence does NOT increase friction (only refusals/disputes do)

**58. Repeat follow-up 3x**
- Simulate 3 silence cycles (180 minutes total)
- Trigger scheduler 2 more times
- Advance time 60+ minutes each cycle

**59. Verify next_action_time extends**
- After each silence cycle, confirm `next_action_time` moves forward
- Scheduler continues to queue new attempts

**60. Send refusal after silence**
- After 3 silence cycles, borrower finally replies: "I refuse"
- SMS webhook: `message: "I refuse"`

**61. Verify phase advance**
- Query case
- Verify: `current_workflow_step = STEP_2`
- Workflow advances despite silence history

**Success criteria:** Silence loop works, randomized messages sent, friction counter stays 0

---

## **PHASE 5: OBJECTION & FRICTION HANDLING** (Days 10-11)

### Steps 62-70: Objection Responses

**62. Test Stop Payment objection**
- SMS webhook: "I put a stop payment at the bank"
- AI should detect objection

**63. Verify AI response**
- Check generated response
- Should ask: "Did you contact your bank to remove the stop payment block?"

**64. Verify payment still requested**
- Confirm response includes original payment demand: "$196.25"
- Do NOT remove payment requirement

**65. Test Closed Account objection**
- SMS webhook: "My account is closed"
- AI should detect objection

**66. Verify AI response**
- Check generated response
- Should ask: "Please upload your new void cheque to restore payments"

**67. Verify payment requested**
- Confirm response includes payment demand
- Document request does NOT replace payment requirement

**68. Test Hardship claim**
- SMS webhook: "I lost my job, can't pay right now"
- AI should detect hardship claim

**69. Verify hardship rejected**
- Check system response
- Should NOT accept inability to pay
- Should NOT offer new arrangement outside payment ladder

**70. Verify next payment option offered**
- Check response offers STEP_2 option (if in STEP_1)
- Empathy shown but payment requirement maintained

**Success criteria:** Objection handling correct, payment always requested

---

### Steps 71-80: Friction Management

**71. Send message 1**
- Borrower responses with objection/difficult exchange
- Mark as friction-inducing

**72. Send messages 2-7**
- Send 6 back-and-forth exchanges
- Each qualifies as friction

**73. Verify friction_count increments**
- After each friction exchange, check `message_friction_count`
- After message 2: count = 1
- After message 3: count = 2
- ... and so on

**74. Send message 8**
- 8th difficult exchange
- After this message, count reaches 8

**75. Verify friction_count = 8**
- Query case
- Confirm: `message_friction_count = 8`

**76. Verify automation_status = HITL**
- Check case status changed
- Verify: `automation_status = "HITL"` (Human-In-The-Loop)

**77. Confirm collections paused**
- Verify no more automatic followup messages queued
- Scheduler should not trigger new messages
- Collections awaiting human action

**78. Notify human**
- Verify alert/notification sent to collections team
- Alert should include case ID, borrower info, friction reason

**79. Human escalation**
- Simulate human collections agent taking over case
- Manual action: update case status or send custom message

**80. Verify collections resume**
- After human action, confirm `automation_status` restored
- If collector sets to ACTIVE, verify scheduler resumes
- Or collector may resolve manually (set to RESOLVED)

**Success criteria:** Friction tracking accurate, HITL triggered at 8

---

## **PHASE 6: LEGAL & COMPLIANCE STOPS** (Days 12-13)

### Steps 81-90: Legal Trigger Detection

**81. Test bankruptcy mention**
- SMS webhook: "I filed for bankruptcy"
- AI should detect legal keyword

**82. Verify legal stop triggered**
- Query case
- Verify: `automation_status = "AUTOMATION_STOPPED"`
- Verify legal flag set

**83. Verify human notified**
- Check alert sent to legal/compliance team (not collections)
- Alert should indicate legal risk

**84. Test lawyer mention**
- SMS webhook: "Talk to my lawyer"
- AI should detect legal keyword

**85. Verify legal stop triggered**
- Query case
- Verify: `automation_status = "AUTOMATION_STOPPED"`

**86. Test identity dispute**
- SMS webhook: "This is wrong person, you have the wrong account"
- AI should detect identity dispute

**87. Verify legal stop triggered**
- Query case
- Verify: `automation_status = "AUTOMATION_STOPPED"`

**88. Verify case marked**
- Check case flagged for legal/compliance review
- Include reason in flag

**89. Verify no more messages sent**
- Confirm automation completely stopped
- No scheduled messages in queue
- No scheduler tasks will execute

**90. Verify case locked**
- Confirm case cannot advance to future phases
- If human tries to advance, system rejects or warns

**Success criteria:** All legal triggers detected, automation stops, case locked

---

### Steps 91-100: Interac Payment Request

**91. Test Interac request**
- SMS webhook: "Can I pay you with Interac e-transfer instead?"
- AI should detect special request

**92. Verify flag_for_human_review = true**
- Query case
- Check: `flag_for_human_review = true`
- `review_reason = "Interac payment request"`

**93. Verify automation halts**
- Confirm scheduled messages stop
- No new automatic SMS/email queued

**94. Verify escalation reason logged**
- Check interaction record
- Verify reason documented

**95. Simulate human review**
- Human collections agent approves Interac payment
- Manual action: update CRM row to trigger E-Transfer status

**96. Update row to Etransfer status**
- Partner calls: `PATCH /api/partner-gateway/v1/crm/row/{row_id}/update/`
- Set Action to "Etransfer" or equivalent
- Set Frequency to match company policy

**97. Verify existing automation runs**
- Confirm Daily→E-Transfer automation triggers
- Automation decision engine processes change
- Row may move to board 71 (E-Transfer board)

**98. Verify row moves to board 71**
- Check row now in board 71
- Confirm group changed appropriately

**99. Verify no duplicate messages**
- Check that same payment message not resent
- Verify message count doesn't spike

**100. Verify payment received tracking**
- When borrower sends Interac payment
- CRM webhook received with Interac confirmation
- Verify payment logged correctly
- Verify case marked RESOLVED when received

**Success criteria:** Interac requests pause automation, automations trigger on approval

---

## **PHASE 7: WEBHOOK INTEGRATION** (Days 14-15)

### Steps 101-110: Outbound Webhook Verification

**101. Configure webhook receiver**
- Set up test webhook listener (ngrok, RequestBin, local test server)
- Configure endpoint: `https://webhook.example.com/icollector`

**102. Update CRM row**
- Partner calls: `PATCH /api/partner-gateway/v1/crm/row/{test_row_id}/update/`
- Change Action column from "Review" to "Etransfer"

**103. Verify webhook fires**
- Check webhook receiver logs
- Confirm `crm.row.updated` event received
- Event should arrive within seconds

**104. Verify signature present**
- Check webhook headers
- Confirm `X-Partner-Signature` header present
- Format: `sha256=<hex>`

**105. Verify timestamp/nonce**
- Check `X-Partner-Timestamp` header present
- Check `X-Partner-Nonce` header present
- Both should be unique per delivery

**106. Verify signature valid**
- Reconstruct canonical string using webhook body and headers
- Compute HMAC using outbound secret
- Verify computed signature matches `X-Partner-Signature`

**107. Verify delivery_id unique**
- Check `X-Partner-Delivery-Id` header
- Verify different for each webhook delivery
- Use for deduplication on receiver side

**108. Send SMS message**
- Partner calls: `POST /api/partner-gateway/v1/sms/send/`
- Send SMS to borrower

**109. Verify webhook: sms.sent**
- Check webhook receiver
- Confirm `sms.sent` event received
- Should include SMS metadata

**110. Verify SMS payload**
- Check event data includes:
  - row_id
  - phone
  - message_id
  - status: "sent"

**Success criteria:** Webhooks fire, signatures valid, all events received

---

### Steps 111-120: Webhook Retry Logic

**111. Mock webhook receiver fails**
- Webhook receiver configured to return `500 Internal Server Error`
- Partner sends CRM update
- Webhook trigger fires

**112. Verify retry attempt**
- Check iCollectorAI logs
- Confirm retry scheduled after timeout/error
- Wait for retry (typically 60-120 seconds)

**113. Mock receiver succeeds**
- Update webhook receiver to return `200 OK`
- Wait for retry attempt

**114. Verify webhook accepted**
- Check retry succeeds (receiver got 200)
- Check iCollectorAI logs mark delivery as success

**115. Test repeated failures**
- Reset receiver to always return 500
- Trigger new CRM update
- Verify retries continue

**116. Verify max retries**
- Confirm delivery eventually stops after N attempts
- Track retry count in logs

**117. Verify delivery logged**
- Check failed delivery marked in system
- Verify attempt count recorded

**118. Test webhook timeout**
- Configure receiver to never respond (hangs indefinitely)
- Trigger CRM update
- Webhook should timeout

**119. Verify timeout triggers retry**
- Confirm retry attempt after timeout
- Verify timeout delay configured (typically 30-60s)

**120. Verify exponential backoff**
- Confirm delays increase between retries
- Pattern: 60s, 120s, 240s, etc.
- Or similar exponential strategy

**Success criteria:** Webhook retries work, backoff implemented, failures logged

---

## **PHASE 8: END-TO-END PRODUCTION SIMULATION** (Days 16-17)

### Steps 121-140: Complete Workflow Cycle

**121. Day 0 09:00 AM** - CRM sends NSF webhook  
- Failed payment: $146.25
- NSF fee: $50
- Total due: $196.25

**122. Verify case in STEP_1**
- Check status ACTIVE, phase STEP_1
- Load CollectionCase from DB
- Confirm automation_status ACTIVE

**123. Verify SMS sent**
- Confirm immediate payment demand ($196.25)
- Tone: courteous, professional
- Include payment options

**124. Day 0 10:30 AM** - Borrower replies "I can't"  
- SMS webhook received

**125. Verify intent detected**
- Check AI analysis: refusal intent
- Confidence score recorded

**126. Verify phase advanced**
- Check case now STEP_2
- Workflow timestamp updated

**127. Verify new SMS sent**
- Check double payment demand ($292.50)
- Tone: urgent, professional
- Clear payment instructions

**128. Day 0 11:00 AM** - Borrower replies "I'll pay next Friday"
- SMS webhook received with commitment

**129. Verify promise detected**
- Check AI analysis: promise_to_pay intent
- High confidence score

**130. Verify PaymentCommitment created**
- Check commitment in DB
- Amount: $292.50
- promised_date: Friday (3 days later)
- status: PENDING

**131. Verify confirmation SMS sent**
- System acknowledges commitment
- Includes commitment date and amount
- Professional tone

**132. Day 3, 3 silence cycles** - No response received
- Time advances 60+ minutes each cycle
- Scheduler triggers 3 times

**133. Verify randomized reminders**
- Check 3+ follow-up messages sent
- Messages vary in wording
- Each references commitment

**134. Verify friction = 0**
- Check friction counter still 0
- Silence does not count as friction

**135. Day 5 09:00 AM** - Scheduled commitment check runs
- Execute: check_commitment_fulfillment() task
- promised_date is today

**136. Verify payment still due**
- Confirm no payment received
- Check TransactionLedger for Day 5 (no payment)

**137. Verify commitment status**
- Check status changed to BROKEN
- Record timestamp of breakage

**138. Verify workflow escalation**
- If configured, check case escalated (e.g., friction marker)
- Or check next phase queued to send

**139. Day 5 09:30 AM** - New escalation message sent
- System sends escalation message
- Tone: firm, final
- May include threat of legal action or account closure

**140. Verify case progresses**
- Check case ready for next action
- Scheduler updated for next contact attempt

**Success criteria:** Complete real-world cycle works correctly

---

### Steps 141-160: Error Scenarios & Recovery

**141. Simulate API timeout**
- Mock SMS provider API to timeout (no response)
- Partner sends SMS via `/api/partner-gateway/v1/sms/send/`

**142. Verify retry logic**
- Check Celery task retried with backoff
- Verify exponential backoff applied

**143. Verify case not stuck**
- Check case `next_action_time` not blocked
- Future messages still queued

**144. Simulate invalid phone**
- Send SMS to malformed phone number (e.g., "abc123")
- API call made

**145. Verify error logged**
- Check error recorded in interaction_ledger
- Interaction marked FAILED
- Error reason documented

**146. Verify fallback**
- Check next channel attempted (e.g., email)
- Or manual review flag set
- Case does not halt

**147. Simulate OpenAI unavailable**
- Mock AI API timeout or error response
- Webhook received, AI processing triggered

**148. Verify fallback template used**
- Check generic/template message sent instead of AI-generated
- Message still appropriate and professional

**149. Verify case continues**
- Confirm automation doesn't halt on AI failure
- Case lifecycle continues normally

**150. Simulate database error**
- Force DB connection failure during case update
- Webhook received

**151. Verify transaction rollback**
- Check partial updates don't occur
- Either full update or no update

**152. Verify retry queued**
- Check task retried after DB recovery
- Case eventually updated successfully

**153. Simulate duplicate webhook**
- Send same webhook twice (identical payload, message_id, etc.)
- Both requests include valid signatures

**154. Verify idempotency**
- Check only one CollectionCase created/updated
- Only one InteractionLedger entry
- Duplicate request rejected or marked as idempotent

**155. Verify replay detection**
- Check second request rejected or duplicate noted
- System prevents double-processing

**156. Simulate out-of-order delivery**
- Deliver promise-to-pay webhook before refusal webhook
- Both webhooks arrive but in reverse sequence

**157. Verify state consistency**
- Check workflow state remains valid despite order
- Most recent intent wins or merge logic applied
- No data corruption

**158. Verify logging preserved**
- Check all events logged in received sequence
- Audit trail accurate even if processing out-of-order

**159. Simulate high volume**
- Send 100 webhooks simultaneously
- All simultaneously to `/api/webhooks/sms/`

**160. Verify load handling**
- Check all processed successfully
- No data loss
- No duplicate cases created
- Performance acceptable (< 5 second per request)

**Success criteria:** All error scenarios handled gracefully, recovery works

---

## **TOTAL TESTING SUMMARY**

| Phase | Steps | Duration | Focus |
|-------|-------|----------|-------|
| 1: Gateway Connectivity | 1-20 | 2 days | Authentication, CRM discovery |
| 2: CRM Operations | 11-30 | 2 days | Mutations, row lifecycle |
| 3: Communications | 21-30 | 2 days | SMS, Email dispatch |
| 4: Workflow Simulation | 31-60 | 3 days | STEP_1→2, promises, silence loops |
| 5: Objections & Friction | 61-80 | 2 days | Objection handling, friction tracking |
| 6: Legal & Compliance | 81-100 | 2 days | Legal stops, Interac requests |
| 7: Webhooks | 101-120 | 2 days | Outbound webhooks, retries |
| 8: End-to-End Production | 121-160 | 2 days | Complete cycles, error recovery |

**Total: 160 test cases across 8 phases = ~15 days of testing**

**Estimated Timeline:** 3 weeks with parallel testing, 1 week sequential

---

## **QUICK TEST CHECKLIST**

### Critical Path (Must Pass)
- ✅ Gateway ping & signature validation
- ✅ SMS/Email send to real numbers
- ✅ CRM rows CRUD operations
- ✅ Refusal → phase advance (STEP_1→2)
- ✅ Promise-to-pay → commitment creation
- ✅ Commitment broken → escalation
- ✅ Legal keywords → automation stop
- ✅ Friction count → HITL at 8
- ✅ Outbound webhook signatures valid
- ✅ End-to-end workflow completes

### Blockers (If Any Fail = Cannot Go Live)
- ❌ No SMS/Email actually delivered
- ❌ Workflow doesn't advance on refusal
- ❌ Promises not tracked
- ❌ Legal stops not enforced
- ❌ Webhooks not secure
- ❌ Database corruptions
- ❌ High volume test failures

---

## **Test Execution Notes**

1. **Parallel Testing:** Run phases 1-3 in parallel, then execute 4-8 sequentially
2. **Environment:** Use staging environment with test iCollectorAI credentials
3. **Test Data:** Create dedicated test borrower profiles with valid contact info
4. **Logging:** Enable full logging for all API calls and Celery tasks
5. **Monitoring:** Watch error rates and transaction times during high-volume tests
6. **Documentation:** Record results for each test step with timestamps
7. **Regression:** Re-run critical path tests after any code changes
8. **Rollback:** Have rollback plan if production issues occur

---

**Report Generated:** March 18, 2026  
**Status:** Testing Procedure Complete ✅

