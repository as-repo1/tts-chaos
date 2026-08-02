from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.db.store import save_voice, list_voices, get_voice, delete_voice
from backend.app.services.generator import generate_audio_asset
from backend.app.services.model_selector import auto_select_model
from backend.app.services.model_manager import model_manager

router = APIRouter(prefix="/api", tags=["voices"])


class VoiceCreateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    voice_name: str = Field(default="my-voice")
    language: str = Field(default="en")
    style: str = Field(default="neutral")
    model_id: str | None = None
    voice_id: str = Field(default="default")
    speed: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=0.0, ge=-10.0, le=10.0)
    output_format: str = Field(default="wav")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/voice")
async def create_voice(payload: VoiceCreateRequest) -> dict[str, Any]:
    model_id = payload.model_id or auto_select_model(
        payload.text, payload.language, payload.style, model_manager
    )

    asset = generate_audio_asset(
        text=payload.text,
        voice_name=payload.voice_name,
        language=payload.language,
        style=payload.style,
        model_id=model_id,
        voice_id=payload.voice_id,
        speed=payload.speed,
        pitch=payload.pitch,
        output_format=payload.output_format,
    )

    record = await save_voice(
        voice_name=payload.voice_name,
        language=payload.language,
        style=payload.style,
        text=payload.text,
        model_id=model_id,
        voice_id=payload.voice_id,
        speed=payload.speed,
        pitch=payload.pitch,
        file_path=asset["file_path"],
        file_size=asset["file_size"],
        duration_sec=None,
        output_format=payload.output_format,
    )
    return record


@router.get("/voices")
async def get_voices(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    voices = await list_voices(offset=offset, limit=limit)
    return {"voices": voices, "offset": offset, "limit": limit}


@router.get("/voices/{voice_id}/audio")
async def stream_audio(voice_id: str) -> FileResponse:
    record = await get_voice(voice_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Voice not found")
    path = Path(record["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing")
    media_type = "audio/mpeg" if record["output_format"] == "mp3" else "audio/wav"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete("/voices/{voice_id}")
async def remove_voice(voice_id: str) -> dict[str, str]:
    record = await get_voice(voice_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Voice not found")
    Path(record["file_path"]).unlink(missing_ok=True)
    await delete_voice(voice_id)
    return {"status": "deleted", "id": voice_id}
