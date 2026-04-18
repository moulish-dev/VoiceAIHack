# VoiceAIHack

Minimal local demo for streaming microphone audio to a Python backend, relaying it to Speechmatics realtime transcription, and showing transcript output in a simple browser frontend.

## Requirements

- Python 3.14+
- A Speechmatics API key

## Setup

1. Create backend env vars:

```bash
cd backend
cp .env.example .env
```

2. Edit `backend/.env` and set:

```env
SPEECHMATICS_API_KEY=your_key_here
```

`THYMIA_API_KEY` is optional right now. If it is unset, the backend sends placeholder `analysis.update` events.

3. Create a virtual environment and install backend dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

Start the backend:

```bash
cd backend
source .venv/bin/activate
python3 app.py
```

Start the frontend static server in another terminal:

```bash
cd frontend
python3 -m http.server 5500
```

Open:

```text
http://127.0.0.1:5500
```

## How To Test

1. Click `Start Recording`.
2. Allow microphone access in the browser.
3. Speak and watch partial/final transcript output appear.
4. Click `Stop Recording` when finished.

## Endpoints

- `GET /health`
- `POST /v1/sessions`
- `WS /v1/sessions/{session_id}/stream`

The websocket expects binary `PCM16 mono 16kHz` audio chunks from the frontend.
