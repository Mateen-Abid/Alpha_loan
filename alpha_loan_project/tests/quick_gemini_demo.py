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

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Import the GeminiClient
from apps.ai.clients.gemini_client import GeminiClient


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
    """Quick demo of Gemini message generation using GeminiClient for all 4 waves."""
    
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
    
    # Initialize GeminiClient
    try:
        client = GeminiClient(api_key=api_key)
    except ImportError:
        print("\n❌ Missing google.genai")
        print("   Install with: pip install google.genai")
        return
    
    # Display demo header
    print("\n" + "="*80)
    print("🤖 GEMINI AI MESSAGE GENERATION - ALL 4 WAVES (HUMANIZED)")
    print("="*80)
    print(f"\n📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 API Key: {api_key[:15]}...{api_key[-5:]}")
    print(f"✅ Gemini configured successfully\n")
    
    # Test all 4 waves with different borrowers
    test_cases = [
        {"name": "Maria Gonzalez", "failed_amount": 525.50, "nsf_fee": 50.00, "wave": 1, "reason": "EFT Failed Insufficient Funds"},
        {"name": "John Smith", "failed_amount": 1200.00, "nsf_fee": 75.00, "wave": 2, "reason": "EFT Failed Stop Payment"},
        {"name": "Sarah Johnson", "failed_amount": 800.00, "nsf_fee": 50.00, "wave": 3, "reason": "EFT Failed Account Closed"},
        {"name": "Robert Chen", "failed_amount": 2500.00, "nsf_fee": 100.00, "wave": 4, "reason": "EFT Failed Insufficient Funds"},
    ]
    
    results = []
    
    for idx, test_case in enumerate(test_cases, 1):
        borrower = test_case["name"]
        total_due = test_case["failed_amount"] + test_case["nsf_fee"]
        wave = test_case["wave"]
        
        wave_names = {1: "Initial Contact (Friendly)", 2: "Second Notice (Firm)", 3: "Legal Escalation (Urgent)", 4: "Final Pressure (Very Urgent)"}
        
        print(f"\n{'='*80}")
        print(f"WAVE {wave} - {wave_names.get(wave, 'Unknown')}")
        print(f"{'='*80}")
        print(f"📋 Borrower: {borrower}")
        print(f"   Failed Payment: ${test_case['failed_amount']:.2f}")
        print(f"   NSF Fee: ${test_case['nsf_fee']:.2f}")
        print(f"   Total Due: ${total_due:.2f}")
        print(f"   Reason: {test_case['reason']}")
        
        # Generate message
        message = client.generate_collection_message(
            borrower_name=borrower,
            failed_amount=test_case["failed_amount"],
            nsf_fee=test_case["nsf_fee"],
            current_balance=total_due,
            reason=test_case["reason"],
            wave=wave,
            tone="professional_friendly"
        )
        
        print(f"\n✅ MESSAGE GENERATED:\n")
        print("┌" + "─"*78 + "┐")
        for line in message.split("\n"):
            print(f"│ {line:<76} │")
        print("└" + "─"*78 + "┘")
        
        print(f"\n📏 Message Length: {len(message)} characters", end="")
        if len(message) <= 160:
            print(" ✅ SMS Compatible (≤160 chars)")
        else:
            print(f" ⚠️  Exceeds SMS limit by {len(message) - 160} chars")
        
        results.append({
            "wave": wave,
            "borrower": borrower,
            "total_due": total_due,
            "message": message,
            "length": len(message),
        })
    
    # Summary
    print(f"\n\n{'='*80}")
    print("📊 SUMMARY - ALL 4 WAVES")
    print(f"{'='*80}\n")
    
    for result in results:
        print(f"Wave {result['wave']} - {result['borrower']} (${result['total_due']:,.2f}) - {result['length']} chars")
        print(f"  {result['message']}\n")
    
    print(f"{'='*80}")
    print("✅ DEMO COMPLETE - All waves generated!")
    print(f"{'='*80}\n")


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
