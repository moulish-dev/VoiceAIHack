from __future__ import annotations

import asyncio
from contextlib import suppress

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState

from config import get_settings
from speechmatics_api import (
    BiomarkerProvider,
    SessionManager,
    SpeechmaticsRealtimeClient,
    normalize_transcript_event,
)

settings = get_settings()
app = FastAPI(title="VoiceAIHack Backend", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5500"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sessions = SessionManager()
biomarkers = BiomarkerProvider(settings)


@app.get("/health")
async def health() -> dict[str, object]:
    return {
        "ok": True,
        "speechmatics_configured": bool(settings.speechmatics_api_key),
        "thymia_configured": bool(settings.thymia_api_key),
    }


@app.post("/v1/sessions")
async def create_session() -> dict[str, str]:
    session = sessions.create()
    return {
        "session_id": session.session_id,
        "ws_url": (
            f"ws://{settings.host}:{settings.port}/v1/sessions/{session.session_id}/stream"
        ),
    }


@app.websocket("/v1/sessions/{session_id}/stream")
async def stream_audio(session_id: str, websocket: WebSocket) -> None:
    session = sessions.get(session_id)
    if session is None:
        await websocket.close(code=4404, reason="Unknown session")
        return

    await websocket.accept()
    client = SpeechmaticsRealtimeClient(settings)
    receiver_task: asyncio.Task[None] | None = None

    try:
        await client.connect()
        receiver_task = asyncio.create_task(
            _forward_speechmatics_messages(client, session.session_id, websocket, session)
        )
        await _safe_send_json(
            websocket,
            {
                "type": "session.ready",
                "session_id": session.session_id,
                "provider": "speechmatics",
            }
        )

        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            audio_bytes = message.get("bytes")
            if audio_bytes is None:
                continue

            await client.send_audio(audio_bytes)
            session.audio_buffer.extend(audio_bytes)
            duration_ms = int(len(audio_bytes) / (settings.sample_rate_hz * 2) * 1000)
            session.buffered_duration_ms += duration_ms
            await biomarkers.maybe_analyze(session, websocket)

        await client.finish()
        if receiver_task:
            await receiver_task
        await _safe_send_json(
            websocket,
            {"type": "session.completed", "session_id": session.session_id}
        )
    except WebSocketDisconnect:
        with suppress(Exception):
            await client.finish()
    except Exception as exc:
        await _safe_send_json(
            websocket,
            {
                "type": "session.error",
                "session_id": session.session_id,
                "message": str(exc),
            }
        )
    finally:
        if receiver_task:
            receiver_task.cancel()
            with suppress(Exception):
                await receiver_task
        sessions.remove(session_id)
        with suppress(Exception):
            await client.close()
        with suppress(Exception):
            await websocket.close()


async def _forward_speechmatics_messages(
    client: SpeechmaticsRealtimeClient,
    session_id: str,
    websocket: WebSocket,
    session,
) -> None:
    while True:
        payload = await client.receive_message()
        message_type = payload.get("message")

        if message_type == "EndOfTranscript":
            return

        event = normalize_transcript_event(payload, session_id)
        if event is None:
            continue

        if event["is_final"] and event["text"]:
            session.final_transcript_parts.append(event["text"])
        await _safe_send_json(websocket, event)


async def _safe_send_json(websocket: WebSocket, payload: dict[str, object]) -> bool:
    if websocket.client_state == WebSocketState.DISCONNECTED:
        return False
    try:
        await websocket.send_json(payload)
        return True
    except RuntimeError:
        return False


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host=settings.host, port=settings.port, reload=False)
