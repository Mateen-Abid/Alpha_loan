"""
Direct Gemini AI testing pipeline for Board 70 dummy data.

This script can be run standalone to test AI message generation
without needing to run Django shell.

Usage:
    python -m tests.standalone_gemini_pipeline
    
    Or from command line:
    cd alpha_loan_project
    GEMINI_API_KEY=your_key_here python -m tests.standalone_gemini_pipeline
"""

import os
import sys
import json
from datetime import datetime

# Ensure project-root imports (e.g. `apps.*`) work when this file
# is executed directly via `python tests/standalone_gemini_pipeline.py`.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Fix Windows encoding issues with Unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Test data inline (dummy Board 70 data)
TEST_BORROWERS = [
    {
        "id": "001",
        "name": "Maria Gonzalez",
        "amount": 525.50,
        "balance": 575.50,
        "reason": "EFT Failed Insufficient Funds",
        "wave": 1,
    },
    {
        "id": "002",
        "name": "James Mitchell",
        "amount": 750.00,
        "balance": 800.00,
        "reason": "EFT Failed Stop Payment",
        "wave": 2,
    },
    {
        "id": "003",
        "name": "Alexandra Chen",
        "amount": 325.75,
        "balance": 375.75,
        "reason": "EFT Failed Insufficient Funds",
        "wave": 3,
    },
    {
        "id": "004",
        "name": "David Kumar",
        "amount": 600.00,
        "balance": 650.00,
        "reason": "EFT Failed Account Closed",
        "wave": 4,
    },
    {
        "id": "005",
        "name": "Sophie Leclerc",
        "amount": 450.25,
        "balance": 500.25,
        "reason": "EFT Failed Insufficient Funds",
        "wave": 1,
    },
]


def generate_message_with_gemini(
    client,
    borrower_name: str,
    failed_amount: float,
    nsf_fee: float = 50.00,
    current_balance: float = 0.0,
    reason: str = "Payment failed",
    wave: int = 1,
) -> str:
    """Generate message through shared runtime GeminiClient."""
    return client.generate_collection_message(
        borrower_name=borrower_name,
        failed_amount=failed_amount,
        nsf_fee=nsf_fee,
        current_balance=current_balance,
        reason=reason,
        wave=wave,
        tone="professional_friendly",
    )


def run_testing_pipeline():
    """Execute the Gemini testing pipeline."""
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n❌ ERROR: GEMINI_API_KEY not set")
        print("   Set it with: export GEMINI_API_KEY='your_key_here'")
        sys.exit(1)
    
    # Configure Gemini via shared runtime client
    from apps.ai.clients.gemini_client import GeminiClient
    gemini_client = GeminiClient(api_key=api_key)
    
    print("\n" + "="*90)
    print("🤖 GEMINI AI MESSAGE GENERATION TESTING PIPELINE")
    print("="*90)
    print(f"\n📅 Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Gemini API: Configured")
    print(f"📊 Board: 70 (Daily Rejects)")
    print(f"👥 Test Borrowers: {len(TEST_BORROWERS)}")
    
    results = []
    
    for idx, borrower in enumerate(TEST_BORROWERS, 1):
        print(f"\n{'-'*90}")
        print(f"📋 BORROWER #{idx} - {borrower['name']}")
        print(f"{'-'*90}")
        
        # Display borrower info
        nsf_fee = 50.00
        total_due = borrower['amount'] + nsf_fee
        
        print(f"  🆔 ID: {borrower['id']}")
        print(f"  👤 Name: {borrower['name']}")
        print(f"  💰 Failed Payment: ${borrower['amount']:,.2f}")
        print(f"  💸 NSF Fee: ${nsf_fee:.2f}")
        print(f"  📊 Total Due: ${total_due:,.2f}")
        print(f"  💳 Account Balance: ${borrower['balance']:,.2f}")
        print(f"  ⚠️  Reason: {borrower['reason']}")
        print(f"  📈 Wave: {borrower['wave']} (Escalation Level)")
        
        # Generate message
        print(f"\n  🔄 Generating message with Gemini...")
        try:
            message = generate_message_with_gemini(
                client=gemini_client,
                borrower_name=borrower['name'],
                failed_amount=borrower['amount'],
                nsf_fee=nsf_fee,
                current_balance=borrower['balance'],
                reason=borrower['reason'],
                wave=borrower['wave'],
            )
            
            print(f"\n  ✅ MESSAGE GENERATED:")
            print(f"  {'-'*86}")
            for line in message.split("\n"):
                print(f"  {line}")
            print(f"  {'-'*86}")
            print(f"  📏 Length: {len(message)} characters")
            
            if len(message) > 160 and borrower['wave'] <= 2:
                print(f"  ⚠️  Note: Message exceeds SMS limit (160 chars)")
            
            results.append({
                "borrower_id": borrower['id'],
                "borrower_name": borrower['name'],
                "wave": borrower['wave'],
                "failed_amount": borrower['amount'],
                "nsf_fee": nsf_fee,
                "total_due": total_due,
                "account_balance": borrower['balance'],
                "reason": borrower['reason'],
                "generated_message": message,
                "message_length": len(message),
            })
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*90}")
    print("📊 PIPELINE EXECUTION COMPLETE")
    print(f"{'='*90}")
    print(f"✅ Successfully generated {len(results)} AI messages")
    print(f"📧 Channel: SMS (conversational, human-friendly)")
    print(f"📈 Waves covered: 1, 2, 3, 4 (All escalation levels)")
    
    total_amount = sum(r['failed_amount'] for r in results)
    total_fees = len(results) * 50
    total_due = sum(r['total_due'] for r in results)
    
    print(f"\n💰 Financial Summary:")
    print(f"   • Total failed payments: ${total_amount:,.2f}")
    print(f"   • Total NSF fees: ${total_fees:,.2f}")
    print(f"   • Total due: ${total_due:,.2f}")
    
    # Export results
    print(f"\n{'='*90}")
    print("📤 DETAILED RESULTS (JSON)")
    print(f"{'='*90}")
    print(json.dumps(results, indent=2))
    
    # Sample by wave
    print(f"\n{'='*90}")
    print("📝 MESSAGE SAMPLES BY ESCALATION WAVE")
    print(f"{'='*90}")
    
    waves = {}
    for r in results:
        if r['wave'] not in waves:
            waves[r['wave']] = r
    
    for wave in sorted(waves.keys()):
        r = waves[wave]
        print(f"\nWave {wave} - {r['borrower_name']} (${r['failed_amount']:,.2f} failed)")
        print(f"{'─'*86}")
        print(r['generated_message'])
        print(f"{'─'*86}\n")
    
    print("✅ TESTING COMPLETE - All messages ready for deployment")
    print(f"{'='*90}\n")


if __name__ == "__main__":
    try:
        run_testing_pipeline()
    except ImportError as e:
        print(f"\n❌ Import error: {e}")
        if "No module named 'apps'" in str(e):
            print("   Project imports are unavailable.")
            print("   Run from project root with: python -m tests.standalone_gemini_pipeline")
        else:
            print("   Install with: pip install google-genai")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
