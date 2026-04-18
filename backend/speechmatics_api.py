from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import websockets
from fastapi import WebSocket

from config import Settings


def _ms_from_seconds(value: float | int | None) -> int | None:
    if value is None:
        return None
    return int(float(value) * 1000)


def _transcript_text(message: dict[str, Any]) -> str:
    metadata = message.get("metadata") or {}
    if metadata.get("transcript"):
        return str(metadata["transcript"])

    chunks: list[str] = []
    for result in message.get("results", []):
        alternatives = result.get("alternatives") or []
        if not alternatives:
            continue
        content = alternatives[0].get("content")
        if content:
            chunks.append(str(content))
    return " ".join(chunks).strip()


def normalize_transcript_event(
    provider_message: dict[str, Any], session_id: str
) -> dict[str, Any] | None:
    kind = provider_message.get("message")
    if kind not in {"AddPartialTranscript", "AddTranscript"}:
        return None

    metadata = provider_message.get("metadata") or {}
    text = _transcript_text(provider_message)
    return {
        "type": "transcript.partial"
        if kind == "AddPartialTranscript"
        else "transcript.final",
        "session_id": session_id,
        "text": text,
        "is_final": kind == "AddTranscript",
        "start_ms": _ms_from_seconds(metadata.get("start_time")),
        "end_ms": _ms_from_seconds(metadata.get("end_time")),
        "provider": "speechmatics",
        "raw": provider_message,
    }


class SpeechmaticsRealtimeClient:
    def __init__(self, settings: Settings, language: str = "en") -> None:
        if not settings.speechmatics_api_key:
            raise RuntimeError(
                "Missing SPEECHMATICS_API_KEY or Speechmatics_API_key in backend/.env"
            )
        self._settings = settings
        self._language = language
        self._connection: Any | None = None
        self._audio_seq_no = 0

    async def connect(self) -> None:
        self._connection = await websockets.connect(
            self._settings.speechmatics_rt_url,
            additional_headers={
                "Authorization": f"Bearer {self._settings.speechmatics_api_key}"
            },
            max_size=None,
        )

        await self._connection.send(
            json.dumps(
                {
                    "message": "StartRecognition",
                    "audio_format": {
                        "type": "raw",
                        "encoding": "pcm_s16le",
                        "sample_rate": self._settings.sample_rate_hz,
                    },
                    "transcription_config": {
                        "language": self._language,
                        "enable_partials": True,
                        "max_delay": 1,
                    },
                }
            )
        )

        while True:
            started = await self._connection.recv()
            if isinstance(started, bytes):
                continue
            payload = json.loads(started)
            message_type = payload.get("message")
            if message_type == "RecognitionStarted":
                return
            if message_type in {"Info", "Warning"}:
                continue
            raise RuntimeError(
                f"Speechmatics session failed to start: {json.dumps(payload)}"
            )

    async def send_audio(self, audio_chunk: bytes) -> None:
        if not self._connection:
            raise RuntimeError("Speechmatics websocket is not connected")
        self._audio_seq_no += 1
        await self._connection.send(audio_chunk)

    async def receive_message(self) -> dict[str, Any]:
        if not self._connection:
            raise RuntimeError("Speechmatics websocket is not connected")
        payload = await self._connection.recv()
        if isinstance(payload, bytes):
            raise RuntimeError("Unexpected binary payload from Speechmatics")
        return json.loads(payload)

    async def finish(self) -> None:
        if not self._connection:
            return
        await self._connection.send(
            json.dumps(
                {
                    "message": "EndOfStream",
                    "last_seq_no": self._audio_seq_no,
                }
            )
        )

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None


@dataclass(slots=True)
class SessionState:
    session_id: str
    started_at: float
    audio_buffer: bytearray = field(default_factory=bytearray)
    final_transcript_parts: list[str] = field(default_factory=list)
    buffered_duration_ms: int = 0
    analysis_runs: int = 0


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self) -> SessionState:
        session = SessionState(session_id=str(uuid.uuid4()), started_at=time.monotonic())
        self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> SessionState | None:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class BiomarkerProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def maybe_analyze(
        self,
        state: SessionState,
        websocket: WebSocket,
    ) -> None:
        threshold_ms = self._settings.analysis_window_seconds * 1000
        if state.buffered_duration_ms < threshold_ms:
            return

        state.analysis_runs += 1
        window_index = state.analysis_runs
        transcript = " ".join(state.final_transcript_parts).strip()
        rms = self._estimate_rms(bytes(state.audio_buffer))

        payload = {
            "type": "analysis.update",
            "session_id": state.session_id,
            "model": "local-placeholder"
            if not self._settings.thymia_api_key
            else "thymia-pending",
            "window_start_ms": max(0, (window_index - 1) * threshold_ms),
            "window_end_ms": window_index * threshold_ms,
            "provider": "local"
            if not self._settings.thymia_api_key
            else "thymia",
            "results": {
                "note": (
                    "THYMIA_API_KEY is not configured, so this is a local placeholder "
                    "analysis event."
                    if not self._settings.thymia_api_key
                    else "THYMIA_API_KEY is configured, but the API adapter is still a "
                    "placeholder until exact endpoint details are wired in."
                ),
                "audio_rms": round(rms, 6),
                "final_transcript_so_far": transcript,
            },
        }
        await websocket.send_json(payload)

        bytes_per_second = self._settings.sample_rate_hz * 2
        window_bytes = bytes_per_second * self._settings.analysis_window_seconds
        del state.audio_buffer[:window_bytes]
        state.buffered_duration_ms = max(0, state.buffered_duration_ms - threshold_ms)

    @staticmethod
    def _estimate_rms(audio_bytes: bytes) -> float:
        if len(audio_bytes) < 2:
            return 0.0

        sample_count = len(audio_bytes) // 2
        total = 0.0
        for idx in range(0, sample_count * 2, 2):
            sample = int.from_bytes(audio_bytes[idx : idx + 2], "little", signed=True)
            total += float(sample * sample)
        mean_square = total / sample_count
        return math.sqrt(mean_square) / 32768.0
