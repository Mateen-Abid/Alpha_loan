"""Test SMS Webhook Endpoint"""

import requests
import json

# SMS Webhook Test Payload
url = "http://127.0.0.1:8000/api/webhooks/sms/"

payload = {
    "phone": "+15145551234",
    "message": "I can't pay this right now",
    "message_id": "sms_001",
    "external_id": "ext_borrower_001"
}

headers = {
    "Content-Type": "application/json"
}

print("Testing SMS Webhook...")
print(f"URL: {url}")
print(f"Payload: {json.dumps(payload, indent=2)}")
print("\n" + "="*50)

try:
    response = requests.post(url, json=payload, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response:\n{json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"Error: {str(e)}")
