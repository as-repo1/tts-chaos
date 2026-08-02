from __future__ import annotations

import io
import struct
import wave
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

AUDIO_DIR = Path(__file__).resolve().parents[3] / "generated_audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _get_wav_duration(data: bytes) -> float | None:
    """Extract duration in seconds from WAV header bytes."""
    try:
        buf = io.BytesIO(data)
        with wave.open(buf, "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate()
            if rate > 0:
                return round(frames / rate, 2)
    except Exception:
        pass
    return None


def generate_audio_asset(
    text: str,
    voice_name: str,
    language: str,
    style: str,
    model_id: str,
    voice_id: str = "default",
    speed: float = 1.0,
    pitch: float = 0.0,
    output_format: str = "wav",
) -> dict[str, str | int | float | None]:
    from .model_manager import model_manager

    try:
        engine = model_manager.get_engine(model_id)
    except Exception as exc:
        raise RuntimeError(f"Engine '{model_id}' is not available: {exc}") from exc

    try:
        raw_audio = engine.generate(text=text, voice_id=voice_id, speed=speed,
                                     pitch=pitch, language=language)
    except Exception as exc:
        logger.exception("TTS engine '%s' failed during generation", model_id)
        raise RuntimeError(f"Generation failed ({model_id}): {exc}") from exc

    if not raw_audio or len(raw_audio) < 100:
        raise RuntimeError("Engine returned empty or invalid audio data")

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    safe_name = "".join(c if c.isalnum() or c in ("_", "-") else "_" for c in voice_name)
    file_name = f"{safe_name}_{timestamp}.{output_format}"
    file_path = AUDIO_DIR / file_name

    file_path.write_bytes(raw_audio)

    duration = _get_wav_duration(raw_audio)

    return {
        "file_name": file_name,
        "file_path": str(file_path),
        "model_id": model_id,
        "voice_name": voice_name,
        "file_size": len(raw_audio),
        "duration_sec": duration,
    }
