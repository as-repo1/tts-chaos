from __future__ import annotations

import io, wave
from pathlib import Path
from datetime import datetime

AUDIO_DIR = Path(__file__).resolve().parents[3] / "generated_audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)


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
) -> dict[str, str]:
    from .model_manager import model_manager

    engine = model_manager.get_engine(model_id)
    raw_wav = engine.generate(text=text, voice_id=voice_id, speed=speed,
                               pitch=pitch, language=language)

    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    safe_name = voice_name.replace(" ", "_")
    file_name = f"{safe_name}_{timestamp}.{output_format}"
    file_path = AUDIO_DIR / file_name

    file_path.write_bytes(raw_wav)

    return {
        "file_name": file_name,
        "file_path": str(file_path),
        "model_id": model_id,
        "voice_name": voice_name,
        "file_size": len(raw_wav),
    }
