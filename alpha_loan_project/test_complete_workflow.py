"""Complete Webhook Testing Suite - Phase 4 Workflow"""

import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_create_collection_case():
    """Test 31: Create new CollectionCase via CRM webhook"""
    print("\n" + "="*60)
    print("TEST 31: Create CollectionCase via CRM Webhook")
    print("="*60)
    
    url = f"{BASE_URL}/api/webhooks/crm/"
    payload = {
        "row_id": 12001,
        "board_id": 70,
        "phone": "+15145551234",
        "email": "borrower@example.com",
        "event_type": "created",
        "external_id": "ext_borrower_001",
        "failed_payment_amount": 146.25,
        "return_reason": "nsf"
    }
    
    print(f"Creating case...")
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

def test_sms_refusal():
    """Test 36: Borrower sends refusal response"""
    print("\n" + "="*60)
    print("TEST 36: Borrower SMS Refusal")
    print("="*60)
    
    url = f"{BASE_URL}/api/webhooks/sms/"
    payload = {
        "phone": "+15145551234",
        "message": "I can't pay this right now",
        "message_id": "sms_001",
        "external_id": "ext_borrower_001"
    }
    
    print(f"Sending refusal SMS...")
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

def test_promise_to_pay():
    """Test 42: Borrower agrees to payment"""
    print("\n" + "="*60)
    print("TEST 42: Borrower SMS Promise-to-Pay")
    print("="*60)
    
    url = f"{BASE_URL}/api/webhooks/sms/"
    payload = {
        "phone": "+15145551234",
        "message": "OK, I'll do that",
        "message_id": "sms_002",
        "external_id": "ext_borrower_001"
    }
    
    print(f"Sending promise SMS...")
    response = requests.post(url, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

if __name__ == "__main__":
    print("\n\n")
    print("╔" + "="*58 + "╗")
    print("║ ALPHA LOANS COLLECTIONS - PHASE 4 TESTING SUITE │")
    print("║ (Steps 31-42: Workflow Simulation)              │")
    print("╚" + "="*58 + "╝")
    
    # Test 31: Create collection case
    case_response = test_create_collection_case()
    
    # Wait a moment
    time.sleep(1)
    
    # Test 36: Send refusal
    test_sms_refusal()
    
    # Maybe in a real scenario we'd wait and then send a promise
    # time.sleep(2)
    # test_promise_to_pay()
    
    print("\n\n✅ Testing Complete!")
    print("\nNext: Check database for created case and interactions")
