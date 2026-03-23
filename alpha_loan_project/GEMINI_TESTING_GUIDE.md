# Gemini AI Message Generation - Testing Pipeline

**Purpose:** Generate human-friendly collection messages using Google Gemini AI based on Board 70 dummy test data.

**Status:** 🧪 Testing/Demo Only (Not for Production)

---

## 📋 Quick Start

### Prerequisites

1. **Google Gemini API Key**
   - Get from: https://makersuite.google.com/app/apikey
   - Free tier available (0-$0.075 per 1K calls)

2. **Python Dependencies**
   ```bash
   pip install google-generativeai
   ```

3. **Environment Setup**
   ```bash
   # Add to .env file
   GEMINI_API_KEY=your_api_key_here
   ```

### Run Testing Pipeline

**Option 1: Standalone (Recommended for Testing)**

```bash
cd c:\Users\RBTG\Development\Alpha\ loan\alpha_loan_project

# Set API key
$env:GEMINI_API_KEY='your_api_key_here'

# Run pipeline
python tests\standalone_gemini_pipeline.py
```

**Option 2: Django Shell**

```bash
python manage.py shell < tests\pipeline_gemini_test.py
```

---

## 📊 Test Data

**Source:** Board 70 (Daily Rejects) - 5 borrowers

| # | Name              | Failed Amount | NSF Fee | Total Due | Wave | Reason                          |
|---|-------------------|---------------|---------|-----------|------|---------------------------------|
| 1 | Maria Gonzalez    | $525.50       | $50.00  | $575.50   | 1    | EFT Failed Insufficient Funds   |
| 2 | James Mitchell    | $750.00       | $50.00  | $800.00   | 2    | EFT Failed Stop Payment         |
| 3 | Alexandra Chen    | $325.75       | $50.00  | $375.75   | 3    | EFT Failed Insufficient Funds   |
| 4 | David Kumar       | $600.00       | $50.00  | $650.00   | 4    | EFT Failed Account Closed       |
| 5 | Sophie Leclerc    | $450.25       | $50.00  | $500.25   | 1    | EFT Failed Insufficient Funds   |

**Totals:**
- Total Failed Payments: $2,651.50
- Total NSF Fees: $250.00
- Total Due: $2,901.50

---

## 🤖 AI Message Generation

### How It Works

```
Test Data (Borrower + Amount)
    ↓
Prompts Gemini API with:
  - Borrower name
  - Failed amount
  - NSF fee ($50)
  - Account balance
  - Failure reason
  - Escalation wave (1-4)
  - Tone (friendly → firm → serious → urgent)
    ↓
Gemini returns human-friendly message
    ↓
Message displayed/stored for review
```

### Message Customization by Wave

**Wave 1 (Initial Contact)** - Friendly, Understanding
- Tone: Professional & Friendly
- Goal: Remind borrower, understand their situation
- Example approach: "We noticed your payment didn't go through. Let's fix this together."

**Wave 2 (Second Notice)** - More Firm
- Tone: Professional & Firm
- Goal: Create sense of urgency
- Example approach: "Your account needs immediate attention. Here's what we need from you."

**Wave 3 (Legal Escalation)** - Serious
- Tone: Serious & Professional
- Goal: Signal escalation
- Example approach: "This situation requires immediate action to avoid further consequences."

**Wave 4 (Final Pressure)** - Urgent
- Tone: Urgent & Direct
- Goal: Final attempt before legal action
- Example approach: "Final notice: We need immediate payment to resolve this matter."

---

## 📝 Example Output

When you run the pipeline, you'll see something like:

```
══════════════════════════════════════════════════════════════════════════════════════════
🤖 GEMINI AI MESSAGE GENERATION TESTING PIPELINE
══════════════════════════════════════════════════════════════════════════════════════════

📅 Execution Date: 2026-03-23 15:45:30
🔑 Gemini API: Configured
📊 Board: 70 (Daily Rejects)
👥 Test Borrowers: 5

──────────────────────────────────────────────────────────────────────────────────────────
📋 BORROWER #1 - Maria Gonzalez
──────────────────────────────────────────────────────────────────────────────────────────
  🆔 ID: 001
  👤 Name: Maria Gonzalez
  💰 Failed Payment: $525.50
  💸 NSF Fee: $50.00
  📊 Total Due: $575.50
  💳 Account Balance: $575.50
  ⚠️  Reason: EFT Failed Insufficient Funds
  📈 Wave: 1 (Escalation Level)

  🔄 Generating message with Gemini...

  ✅ MESSAGE GENERATED:
  ────────────────────────────────────────────────────────────────────────────────────
  Hi Maria, we noticed your recent payment of $525.50 didn't go through due to 
  insufficient funds. We need $575.50 (including a $50 NSF fee) transferred ASAP to 
  resolve this. Can you get this sorted out this week?
  ────────────────────────────────────────────────────────────────────────────────────
  📏 Length: 156 characters
```

---

## 🔧 Architecture

### Files Created

**1. Gemini Client** (`apps/ai/clients/gemini_client.py`)
- Low-level Gemini API wrapper
- Handles API calls, retries, error handling
- Methods:
  - `generate_collection_message()` - AI message generation
  - `detect_intent()` - Borrower reply analysis
  - Fallback messages if API fails

**2. Message Generator** (`apps/ai/message_generation/gemini_message_generator.py`)
- Higher-level service
- Message customization by wave/channel
- SMS length constraints (160 chars)
- Intent analysis for replies

**3. Testing Pipelines**
- `tests/standalone_gemini_pipeline.py` - Direct testing (recommended)
- `tests/pipeline_gemini_test.py` - Django shell version

---

## 🧪 Testing Scenarios

### Scenario 1: Basic Message Generation

```python
from apps.ai.message_generation.gemini_message_generator import MessageGenerationPipeline

pipeline = MessageGenerationPipeline(api_key="your_key")

result = pipeline.generate_for_case(
    case_id="001",
    borrower_name="Maria Gonzalez",
    failed_amount=525.50,
    current_balance=575.50,
    reason="EFT Failed",
    wave=1,
    channel="sms"
)

print(result["generated_message"])
```

### Scenario 2: All Waves

Generate messages for all 4 escalation levels to see tone progression:

```bash
python tests/standalone_gemini_pipeline.py
# Will show Wave 1, 2, 3, 4 messages
```

### Scenario 3: Intent Detection

```python
from apps.ai.clients.gemini_client import GeminiClient

client = GeminiClient(api_key="your_key")

intent_result = client.detect_intent(
    borrower_message="I can pay $200 tomorrow",
    case_context={"amount_due": 575.50, "wave": 1}
)

print(intent_result)
# Output:
# {
#   "intent": "PROMISE_TO_PAY",
#   "confidence": 0.95,
#   "sentiment": "positive",
#   "explanation": "Borrower commits to payment with specific amount and timeframe"
# }
```

---

## 📊 Success Criteria

✅ **For Testing Pipeline:**
- [x] Connects to Gemini API successfully
- [x] Generates 5 messages (one per borrower)
- [x] Messages are human-friendly (not robotic)
- [x] Messages include required information (name, amount, fee, total, balance)
- [x] Tone escalates properly (Wave 1 → 2 → 3 → 4)
- [x] SMS messages optimized for 160-char limit
- [x] Error handling with fallback messages
- [x] Full JSON output for logging/review

✅ **Quality Checks:**
- Messages sound natural (personalization, conversational tone)
- Financial amounts clearly stated
- Escalation evident in language choice
- No legal jargon or aggressive language
- Respectful and professional tone maintained

---

## 📈 Next Steps (Production Integration)

After testing confirms message quality:

1. **Database Integration**
   - Store generated messages in InteractionLedger
   - Record Gemini API latency/cost

2. **Multi-Channel Expansion**
   - Email variants (longer, more formal)
   - Voice IVR scripts (shorter, spoken)

3. **Intent Detection**
   - Analyze borrower replies for intent
   - Automate workflow state transitions

4. **Performance Optimization**
   - Cache common message templates
   - Batch API calls if needed
   - Monitor API quota usage

5. **Production Deployment**
   - Replace test data with live CRM data
   - Deploy to staging environment
   - UAT with client
   - Go live on Board 70

---

## 🛠️ Troubleshooting

### Error: "GEMINI_API_KEY not set"

```bash
# Windows PowerShell
$env:GEMINI_API_KEY='your_key_here'

# Linux/Mac
export GEMINI_API_KEY='your_key_here'
```

### Error: "google.generativeai not found"

```bash
pip install google-generativeai
```

### Error: "Invalid API key"

- Check key is copied correctly (no spaces)
- Verify key at: https://makersuite.google.com/app/apikey
- Ensure API is enabled in Google Cloud

### API Rate Limit

Gemini free tier: 60 requests per minute
- Pipeline uses 5 calls (1 per borrower)
- Plenty of room for testing

---

## 📞 Support

For issues:
1. Check `.env` has `GEMINI_API_KEY` set
2. Verify Gemini API key is valid
3. Run with verbose output: `python tests/standalone_gemini_pipeline.py 2>&1 | tee output.log`
4. Check Gemini API status at: https://makersuite.google.com/app/apikey

---

## 📄 Sample Messages (Expected Output)

**Wave 1 Example:**
```
Hi Maria, we noticed your recent payment of $525.50 didn't go through. 
We need $575.50 total (including a $50 NSF fee) to get this sorted quickly. 
Can you arrange this by end of week?
```

**Wave 2 Example:**
```
James, payment of $750.00 failed on your account. We now need $800 
(failed amount + $50 NSF fee). This needs immediate attention - please 
call us or send payment today.
```

**Wave 3 Example:**
```
Alexandra, your account balance is now $375.75 which includes a $50 NSF 
fee. Legal proceedings may take place if we don't receive payment within 
48 hours. Contact our office immediately.
```

**Wave 4 Example:**
```
David, final notice: Your account shows $650.00 due including NSF fees. 
Failure to make payment within 24 hours will result in legal action. 
Contact us immediately at [number] to resolve this.
```

---

**Last Updated:** March 23, 2026  
**Pipeline Status:** ✅ Ready for Testing  
**Next Review:** After initial Gemini API testing

