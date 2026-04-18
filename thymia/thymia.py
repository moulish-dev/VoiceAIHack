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

AUDIO_FOLDER = "audio_files"

def process_audio(audio_path):
    # Step 1: Create run
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
    print(f"  Run created: {model_run_id}")

    # Step 2: Upload
    with open(audio_path, "rb") as f:
        requests.put(upload_url, data=f)
    print(f"  Uploaded: {audio_path}")

    # Step 3: Poll
    for attempt in range(20):
        time.sleep(5)
        result = requests.get(
            f"{BASE_URL}/v1/models/mental-wellness/{model_run_id}",
            headers=HEADERS
        ).json()
        status = result["status"]
        print(f"  [{attempt+1}] {status}")
        if status == "COMPLETE_OK":
            return result
        elif status == "COMPLETE_ERROR":
            print("❌ Error:", result.get("errorCode"))
            return None
    return None

# ── MAIN: process all audio files in folder ──────────────────────────────────
audio_files = sorted([
    f for f in os.listdir(AUDIO_FOLDER)
    if f.endswith((".wav", ".mp3", ".mp4", ".ogg", ".webm", ".flac"))
])

print(f"Found {len(audio_files)} audio files\n")

sessions = load_sessions()

for audio_file in audio_files:
    print(f"\n🎙️ Processing: {audio_file}")
    path   = os.path.join(AUDIO_FOLDER, audio_file)
    result = process_audio(path)

    if result:
        session  = extract_session(result)
        sessions.append(session)
        save_sessions(sessions)

        print(f"\n📊 Biomarkers for {audio_file}:")
        print(f"  distress:    {session['distress']:.2f}")
        print(f"  stress:      {session['stress']:.2f}")
        print(f"  exhaustion:  {session['exhaustion']:.2f}")
        print(f"  sleep:       {session['sleep']:.2f}")
        print(f"  selfEsteem:  {session['selfEsteem']:.2f}")
        print(f"  mentalStrain:{session['mentalStrain']:.2f}")

        analysis = analyse(sessions)
        print(f"\n🧠 After {len(sessions)} sessions:")
        print(json.dumps(analysis, indent=2))
        print("─" * 40)