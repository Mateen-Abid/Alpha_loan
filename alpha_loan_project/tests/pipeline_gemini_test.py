"""
Testing pipeline for Board 70 dummy data with Gemini AI message generation.

This script:
1. Loads Board 70 test data (5 happy path borrowers)
2. For each borrower, generates a collection message using Gemini
3. Displays the full output showing realistic messages
4. Tests the message generation at different escalation waves

Usage:
    python manage.py shell < tests/pipeline_gemini_test.py
    
    Or from within Django shell:
    >>> exec(open('tests/pipeline_gemini_test.py').read())
"""

import os
import json
from decimal import Decimal
from datetime import datetime

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def run_gemini_testing_pipeline():
    """Execute the full testing pipeline."""
    
    # Import after Django setup
    from apps.ai.message_generation.gemini_message_generator import MessageGenerationPipeline
    from tests.fixtures.board70_test_data import BOARD_70_ROWS_RESPONSE
    
    # Get Gemini API key from environment
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        print("\n❌ ERROR: GEMINI_API_KEY environment variable not set")
        print("   Please add GEMINI_API_KEY to your .env file")
        return
    
    print("\n" + "="*80)
    print("🤖 GEMINI AI MESSAGE GENERATION TESTING PIPELINE")
    print("="*80)
    print(f"\n📅 Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Gemini API Key: {gemini_api_key[:10]}...{gemini_api_key[-5:]}")
    print(f"📊 Board: 70 (Daily Rejects)")
    print(f"👥 Test Borrowers: 5 (from dummy test data)")
    
    # Initialize pipeline
    pipeline = MessageGenerationPipeline(gemini_api_key)
    
    # Extract test data
    test_data = BOARD_70_ROWS_RESPONSE.get("results", [])
    print(f"\n📦 Loaded {len(test_data)} test records")
    
    # Process each borrower
    results = []
    for idx, row in enumerate(test_data, 1):
        columns = row.get("columns", {})
        
        # Extract data
        row_id = str(row.get("id", f"row_{idx}"))
        borrower_name = columns.get("Client", f"Borrower {idx}") or f"Borrower {idx}"
        amount = float(columns.get("Amount", 0) or 0)
        balance = float(columns.get("Balance", 0) or 0)
        reason = columns.get("Reason", "EFT Failed")
        wave = int(columns.get("Wave", 1) or 1)
        
        if not amount:
            print(f"\n⏭️  Skipping row {idx} (no amount)")
            continue
        
        # Generate message for this borrower
        print(f"\n{'-'*80}")
        print(f"📋 Borrower #{idx}")
        print(f"{'-'*80}")
        print(f"  ID: {row_id}")
        print(f"  Name: {borrower_name}")
        print(f"  Failed Amount: ${amount:,.2f}")
        print(f"  NSF Fee: $50.00")
        print(f"  Total Due: ${amount + 50:,.2f}")
        print(f"  Account Balance: ${balance:,.2f}")
        print(f"  Reason: {reason}")
        print(f"  Wave: {wave}")
        
        try:
            # Generate message via pipeline
            result = pipeline.generate_for_case(
                case_id=row_id,
                borrower_name=borrower_name,
                failed_amount=amount,
                current_balance=balance,
                reason=reason,
                wave=wave,
                channel="sms",
            )
            
            # Display generated message
            print(f"\n  ✅ Generated Message (SMS):")
            print(f"  " + "─" * 76)
            for line in result["generated_message"].split("\n"):
                print(f"  | {line}")
            print(f"  " + "─" * 76)
            print(f"  📏 Length: {result['message_length']} chars")
            if result['truncated_for_sms']:
                print(f"  ⚠️  Truncated for SMS (max 160 chars)")
            
            results.append(result)
            
        except Exception as e:
            print(f"  ❌ Error generating message: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary
    print(f"\n{'='*80}")
    print("📊 PIPELINE SUMMARY")
    print(f"{'='*80}")
    print(f"✅ Successfully generated {len(results)} messages")
    print(f"📧 Channels: SMS (all)")
    print(f"📈 Waves: {', '.join(sorted(set(r['wave'] for r in results)))}")
    print(f"💰 Total amount at risk: ${sum(r['amounts']['failed_payment'] for r in results):,.2f}")
    print(f"💸 Total NSF fees: ${len(results) * 50:,.2f}")
    print(f"🎯 Total due: ${sum(r['amounts']['total_due'] for r in results):,.2f}")
    
    # Detailed results for export
    print(f"\n{'='*80}")
    print("📤 DETAILED RESULTS (JSON)")
    print(f"{'='*80}")
    print(json.dumps(results, indent=2, default=str))
    
    # Message examples by wave
    print(f"\n{'='*80}")
    print("📝 MESSAGE EXAMPLES BY ESCALATION WAVE")
    print(f"{'='*80}")
    
    waves_seen = {}
    for result in results:
        wave = result['wave']
        if wave not in waves_seen:
            waves_seen[wave] = result
    
    for wave in sorted(waves_seen.keys()):
        result = waves_seen[wave]
        print(f"\nWave {wave} - {result['borrower_name']}:")
        print(f"{'─'*76}")
        print(result['generated_message'])
        print(f"{'─'*76}")
    
    print(f"\n{'='*80}")
    print("✅ TESTING PIPELINE COMPLETE")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    run_gemini_testing_pipeline()
