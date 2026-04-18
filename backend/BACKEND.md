# Backend

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

The backend reads `backend/.env`. It supports both `SPEECHMATICS_API_KEY` and the older `Speechmatics_API_key`.

## Endpoints

- `GET /health`
- `POST /v1/sessions`
- `WS /v1/sessions/{session_id}/stream`

The websocket expects binary `PCM16 mono 16kHz` audio chunks.
