# Frontend

Serve the test UI as static files from `frontend/`.

```bash
cd frontend
python3 -m http.server 5500
```

Then open `http://127.0.0.1:5500`.

The page records microphone audio, streams raw `PCM16 mono 16kHz` chunks to the backend websocket, and shows transcript plus raw event output.
