#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Quick demo script for Gemini AI message generation.

This is the fastest way to test the pipeline.

USAGE:
    1. Get Gemini API key from: https://makersuite.google.com/app/apikey
    2. Set environment variable:
       Windows: $env:GEMINI_API_KEY='your_key'
       Linux/Mac: export GEMINI_API_KEY='your_key'
     3. Install dependency:
         pip install google.genai
    4. Run this script:
       python tests/quick_gemini_demo.py
"""

import os
import sys
import json
from datetime import datetime

# Fix Windows encoding issues with Unicode characters
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Sample borrower for quick demo
DEMO_BORROWER = {
    "name": "Maria Gonzalez",
    "failed_amount": 525.50,
    "nsf_fee": 50.00,
    "balance": 575.50,
    "reason": "EFT Failed Insufficient Funds",
    "wave": 1,
}


def demo_message_generation():
    """Quick demo of Gemini message generation."""
    
    # Check API key
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("\n❌ ERROR: GEMINI_API_KEY not set")
        print("\nQuick Setup:")
        print("  1. Get key: https://makersuite.google.com/app/apikey")
        print("  2. Set it:\n")
        print("     Windows PowerShell:")
        print("     $env:GEMINI_API_KEY='your_key_here'")
        print("\n     Linux/Mac:")
        print("     export GEMINI_API_KEY='your_key_here'")
        print("\n  3. Install: pip install google.genai")
        print("  4. Run: python tests/quick_gemini_demo.py")
        return
    
    try:
        import google.genai as genai
    except ImportError:
        print("\n❌ Missing google.genai")
        print("   Install with: pip install google.genai")
        return
    
    # Configure Gemini client
    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash"
    
    # Display demo header
    print("\n" + "="*80)
    print("🤖 GEMINI AI MESSAGE GENERATION - QUICK DEMO")
    print("="*80)
    print(f"\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key: {api_key[:15]}...{api_key[-5:]}")
    print(f"✅ Gemini configured successfully")
    
    # Display borrower info
    borrower = DEMO_BORROWER
    total_due = borrower["failed_amount"] + borrower["nsf_fee"]
    
    print(f"\n{'─'*80}")
    print("📋 BORROWER DATA")
    print(f"{'─'*80}")
    print(f"  Name: {borrower['name']}")
    print(f"  Failed Payment: ${borrower['failed_amount']:.2f}")
    print(f"  NSF Fee: ${borrower['nsf_fee']:.2f}")
    print(f"  Total Due: ${total_due:.2f}")
    print(f"  Account Balance: ${borrower['balance']:.2f}")
    print(f"  Reason: {borrower['reason']}")
    print(f"  Wave: {borrower['wave']} (Initial Contact)")
    
    # Build prompt
    print(f"\n{'─'*80}")
    print("🔄 GENERATING MESSAGE WITH GEMINI...")
    print(f"{'─'*80}\n")
    
    prompt = f"""
You are a professional collections agent. Generate a HUMAN-FRIENDLY, 
CONVERSATIONAL message to {borrower['name']} about a failed payment.

Details:
- Failed Payment Amount: ${borrower['failed_amount']:.2f}
- NSF Fee: ${borrower['nsf_fee']:.2f}
- Total Due: ${total_due:.2f}
- Account Balance: ${borrower['balance']:.2f}
- Reason: {borrower['reason']}

Make it sound natural and genuine - like a real person helping, not a robot.
Keep it to 2-3 sentences. Include amounts clearly.
Use this exact style:
- Hi {borrower['name']}, we see that your last payment for ${borrower['failed_amount']:.2f} was stopped/failed.
- We need ${borrower['failed_amount']:.2f} + ${borrower['nsf_fee']:.2f} NSF fee now.
- Your current balance is ${borrower['balance']:.2f} + ${borrower['nsf_fee']:.2f} NSF fee.
- End with: to resolve or update payment information.
Do NOT write: "please give us a call", "please call us", or any phone instruction.
Generate ONLY the message, no explanations.
"""
    
    try:
        # Call Gemini API
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        
        if response.text:
            message = response.text.strip()
            for phrase in ["please give us a call", "please call us", "call us", "give us a call"]:
                message = message.replace(phrase, "resolve or update payment information")
                message = message.replace(phrase.title(), "Resolve or update payment information")
            
            print("✅ MESSAGE GENERATED SUCCESSFULLY:\n")
            print("┌" + "─"*78 + "┐")
            for line in message.split("\n"):
                print(f"│ {line:<76} │")
            print("└" + "─"*78 + "┘")
            
            print(f"\n📏 Message Length: {len(message)} characters")
            
            if len(message) <= 160:
                print("✅ SMS Compatible (≤160 chars)")
            else:
                print(f"⚠️  SMS Limit Warning: {len(message) - 160} exceeds 160 char limit")
            
            # Display formatted output
            result = {
                "success": True,
                "borrower": borrower['name'],
                "total_due": total_due,
                "wave": borrower['wave'],
                "generated_message": message,
                "character_count": len(message),
                "sms_compatible": len(message) <= 160,
                "timestamp": datetime.now().isoformat(),
            }
            
            print(f"\n{'─'*80}")
            print("📤 JSON OUTPUT:")
            print(f"{'─'*80}")
            print(json.dumps(result, indent=2))
            
            print(f"\n{'='*80}")
            print("✅ DEMO COMPLETE - Message ready to send!")
            print(f"{'='*80}\n")
            
        else:
            print("❌ No response from Gemini API")
            
    except Exception as e:
        error_text = str(e)
        error_lower = error_text.lower()

        if "429" in error_lower or "resource_exhausted" in error_lower or "quota" in error_lower:
            print(f"❌ Error: {e}")
            print("No fallback message is generated. This output is Gemini-only.")
            print("\nAction required:")
            print("  1. Create/use an API key from a project with available Gemini quota")
            print("  2. Enable billing for that project if required")
            print("  3. Replace GEMINI_API_KEY in .env and rerun")
            print("\nHelpful links:")
            print("  - Quotas: https://ai.google.dev/gemini-api/docs/rate-limits")
            print("  - Usage:  https://ai.dev/rate-limit")
        else:
            print(f"❌ Error: {e}")
            print("No fallback message is generated. This output is Gemini-only.")
            import traceback
            traceback.print_exc()


def demo_full_pipeline():
    """Run demo with all 5 borrowers."""
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        demo_message_generation()
        return
    
    try:
        import google.genai as genai
    except ImportError:
        print("\n❌ Missing dependency: pip install google.genai")
        return
    
    client = genai.Client(api_key=api_key)
    model = "gemini-2.5-flash"
    
    # All 5 borrowers
    borrowers = [
        {"name": "Maria Gonzalez", "amount": 525.50, "balance": 575.50, "reason": "EFT Failed Insufficient Funds", "wave": 1},
        {"name": "James Mitchell", "amount": 750.00, "balance": 800.00, "reason": "EFT Failed Stop Payment", "wave": 2},
        {"name": "Alexandra Chen", "amount": 325.75, "balance": 375.75, "reason": "EFT Failed Insufficient Funds", "wave": 3},
        {"name": "David Kumar", "amount": 600.00, "balance": 650.00, "reason": "EFT Failed Account Closed", "wave": 4},
        {"name": "Sophie Leclerc", "amount": 450.25, "balance": 500.25, "reason": "EFT Failed Insufficient Funds", "wave": 1},
    ]
    
    print("\n" + "="*80)
    print("🤖 GEMINI AI - FULL PIPELINE TEST (5 BORROWERS)")
    print("="*80)
    
    results = []
    
    for idx, borrower in enumerate(borrowers, 1):
        nsf_fee = 50.00
        total_due = borrower["amount"] + nsf_fee
        
        print(f"\n[{idx}/5] {borrower['name']} (Wave {borrower['wave']})...")
        
        prompt = f"""
Generate a natural collection message for {borrower['name']} about a ${borrower['amount']:.2f} 
failed payment. They owe ${total_due:.2f} total (includes $50 NSF fee). 
Wave {borrower['wave']}: {'friendly reminder' if borrower['wave'] == 1 else 'firm notice' if borrower['wave'] == 2 else 'serious' if borrower['wave'] == 3 else 'urgent final notice'}.
Keep it 2-3 sentences, conversational, genuine. Message only, no explanation.
Do NOT write phone instructions. End with: to resolve or update payment information.
"""
        
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            if response.text:
                message = response.text.strip()
                for phrase in ["please give us a call", "please call us", "call us", "give us a call"]:
                    message = message.replace(phrase, "resolve or update payment information")
                    message = message.replace(phrase.title(), "Resolve or update payment information")
                results.append({
                    "borrower": borrower['name'],
                    "wave": borrower['wave'],
                    "total_due": total_due,
                    "message": message,
                })
                print(f"   ✅ Generated ({len(message)} chars)")
            else:
                print(f"   ❌ No response")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Summary
    print(f"\n{'='*80}")
    print(f"📊 RESULTS: {len(results)}/5 messages generated")
    print(f"{'='*80}\n")
    
    for result in results:
        print(f"Wave {result['wave']} - {result['borrower']} (${result['total_due']:,.2f}):")
        print(f"{'─'*76}")
        print(result['message'])
        print()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "full":
        demo_full_pipeline()
    else:
        demo_message_generation()
