import requests
import time
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("THYMIA_API_KEY")
BASE_URL = "https://api.thymia.ai"  # ask Thymia rep if this differs

HEADERS = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

# ── STEP 1: Create a model run ──────────────────────────────────────────────
payload = {
    "user": {
        "userLabel": "test-user-001",
        "dateOfBirth": "1995-01-01",
        "birthSex": "MALE"
    },
    "language": "en-GB"
}

resp = requests.post(f"{BASE_URL}/v1/models/mental-wellness", json=payload, headers=HEADERS)
resp_json = resp.json()
print("STEP 1 - Create run:", resp_json)

model_run_id = resp_json["id"]
upload_url   = resp_json["recordingUploadUrl"]

# ── STEP 2: Upload a test audio file ────────────────────────────────────────
# Need a WAV/MP3 with at least 10 seconds of speech
# Record yourself or use any test audio file
AUDIO_FILE = "thymia/speaker.wav"  # put a real file here

with open(AUDIO_FILE, "rb") as f:
    upload_resp = requests.put(upload_url, data=f)
    print("STEP 2 - Upload status:", upload_resp.status_code)

# ── STEP 3: Poll for results ─────────────────────────────────────────────────
print("STEP 3 - Polling for results...")

for attempt in range(20):
    time.sleep(5)
    result = requests.get(
        f"{BASE_URL}/v1/models/mental-wellness/{model_run_id}",
        headers=HEADERS
    ).json()
    
    status = result["status"]
    print(f"  [{attempt+1}] Status: {status}")
    
    if status == "COMPLETE_OK":
        print("\n✅ FULL RESULT:")
        import json
        print(json.dumps(result, indent=2))
        break
    elif status == "COMPLETE_ERROR":
        print("❌ Error:", result.get("errorReason"), result.get("errorCode"))
        break