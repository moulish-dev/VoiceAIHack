from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


@dataclass(slots=True)
class Settings:
    speechmatics_api_key: str | None
    thymia_api_key: str | None
    speechmatics_rt_url: str
    frontend_origin: str
    host: str
    port: int
    sample_rate_hz: int = 16000
    analysis_window_seconds: int = 15


def get_settings() -> Settings:
    _load_dotenv(Path(__file__).with_name(".env"))
    return Settings(
        speechmatics_api_key=os.getenv("SPEECHMATICS_API_KEY")
        or os.getenv("Speechmatics_API_key"),
        thymia_api_key=os.getenv("THYMIA_API_KEY"),
        speechmatics_rt_url=os.getenv(
            "SPEECHMATICS_RT_URL", "wss://eu2.rt.speechmatics.com/v2"
        ),
        frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5500"),
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
    )
