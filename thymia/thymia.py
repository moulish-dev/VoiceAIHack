import requests
import time
import os
import json
from dotenv import load_dotenv
from drift import load_sessions, save_sessions, extract_session, analyse

load_dotenv()
API_KEY  = os.getenv("THYMIA_API_KEY")
BASE_URL = "https://api.thymia.ai"
HEADERS  = {"x-api-key": API_KEY, "Content-Type": "application/json"}

# ── STEP 1: Create model run ─────────────────────────────────────────────────
payload = {
    "user": {
        "userLabel": "test-user-001",
        "dateOfBirth": "1995-01-01",
        "birthSex": "MALE"
    },
    "language": "en-GB"
}

resp         = requests.post(f"{BASE_URL}/v1/models/mental-wellness", json=payload, headers=HEADERS)
resp_json    = resp.json()
model_run_id = resp_json["id"]
upload_url   = resp_json["recordingUploadUrl"]
print("STEP 1 - Run created:", model_run_id)

# ── STEP 2: Upload audio ──────────────────────────────────────────────────────
AUDIO_FILE = "thymia/speaker.wav"
with open(AUDIO_FILE, "rb") as f:
    upload_resp = requests.put(upload_url, data=f)
print("STEP 2 - Upload status:", upload_resp.status_code)

# ── STEP 3: Poll for results ──────────────────────────────────────────────────
print("STEP 3 - Polling...")
for attempt in range(20):
    time.sleep(5)
    result = requests.get(
        f"{BASE_URL}/v1/models/mental-wellness/{model_run_id}",
        headers=HEADERS
    ).json()

    status = result["status"]
    print(f"  [{attempt+1}] Status: {status}")

    if status == "COMPLETE_OK":
        with open("thymia_result.json", "w") as f:
            json.dump(result, f, indent=2)
        print("💾 Raw result saved to thymia_result.json")

        # ── STEP 4: Extract + save session ───────────────────────────────
        session  = extract_session(result)
        sessions = load_sessions()
        sessions.append(session)
        save_sessions(sessions)
        print(f"📊 Session saved ({len(sessions)} total)")

        # ── STEP 5: Drift analysis ────────────────────────────────────────
        analysis = analyse(sessions)
        print("\n🧠 DRIFT ANALYSIS:")
        print(json.dumps(analysis, indent=2))
        break

    elif status == "COMPLETE_ERROR":
        print("❌ Error:", result.get("errorReason"), result.get("errorCode"))
        break