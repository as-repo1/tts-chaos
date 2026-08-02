from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.db.store import save_voice, list_voices, get_voice, delete_voice, search_voices, count_voices, get_stats
from backend.app.services.generator import generate_audio_asset, generate_cloned_audio_asset
from backend.app.services.model_selector import auto_select_model
from backend.app.services.model_manager import model_manager

logger = logging.getLogger(__name__)

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


class BatchVoiceRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=50)
    voice_name: str = Field(default="batch-voice")
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

    try:
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
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

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
        duration_sec=asset.get("duration_sec"),
        output_format=payload.output_format,
    )
    return record


@router.post("/voice/batch")
async def create_batch_voices(payload: BatchVoiceRequest) -> dict[str, Any]:
    """Generate multiple voices from a list of texts."""
    model_id = payload.model_id or auto_select_model(
        payload.texts[0], payload.language, payload.style, model_manager
    )

    results = []
    errors = []
    for i, text in enumerate(payload.texts):
        text = text.strip()
        if not text:
            continue
        try:
            asset = generate_audio_asset(
                text=text,
                voice_name=f"{payload.voice_name}_{i + 1:03d}",
                language=payload.language,
                style=payload.style,
                model_id=model_id,
                voice_id=payload.voice_id,
                speed=payload.speed,
                pitch=payload.pitch,
                output_format=payload.output_format,
            )
            record = await save_voice(
                voice_name=f"{payload.voice_name}_{i + 1:03d}",
                language=payload.language,
                style=payload.style,
                text=text,
                model_id=model_id,
                voice_id=payload.voice_id,
                speed=payload.speed,
                pitch=payload.pitch,
                file_path=asset["file_path"],
                file_size=asset["file_size"],
                duration_sec=asset.get("duration_sec"),
                output_format=payload.output_format,
            )
            results.append(record)
        except Exception as exc:
            logger.exception("Batch item %d failed", i)
            errors.append({"index": i, "text": text[:80], "error": str(exc)})

    return {"generated": len(results), "errors": errors, "voices": results}


@router.post("/voice/clone")
async def create_cloned_voice(
    text: str = Form(...),
    voice_name: str = Form("cloned-voice"),
    language: str = Form("en"),
    audio_file: UploadFile = File(...)
) -> dict[str, Any]:
    """Clone a voice from an uploaded reference audio file using XTTS v2."""
    
    # Save uploaded reference audio to temporary path
    import tempfile
    import shutil
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        shutil.copyfileobj(audio_file.file, tmp)
        tmp_path = tmp.name
        
    try:
        asset = generate_cloned_audio_asset(
            text=text,
            ref_audio_path=tmp_path,
            voice_name=voice_name,
            language=language,
            model_id="xtts-v2",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        Path(tmp_path).unlink(missing_ok=True)
        
    record = await save_voice(
        voice_name=voice_name,
        language=language,
        style="neutral",
        text=text,
        model_id="xtts-v2",
        voice_id="cloned",
        speed=1.0,
        pitch=0.0,
        file_path=asset["file_path"],
        file_size=asset["file_size"],
        duration_sec=asset.get("duration_sec"),
        output_format="wav",
    )
    return record


@router.get("/voices")
async def get_voices(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    voices = await list_voices(offset=offset, limit=limit)
    total = await count_voices()
    return {"voices": voices, "total": total, "offset": offset, "limit": limit}


@router.get("/voices/search")
async def search_voices_endpoint(
    q: str = Query(default=""),
    model: str = Query(default=""),
    lang: str = Query(default=""),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    voices = await search_voices(query=q, model_id=model, language=lang, offset=offset, limit=limit)
    total = await count_voices(query=q, model_id=model, language=lang)
    return {"voices": voices, "total": total, "offset": offset, "limit": limit}


@router.get("/voices/stats")
async def voice_stats() -> dict[str, Any]:
    stats = await get_stats()
    disk = model_manager.get_disk_usage()
    return {**stats, "disk": disk}


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
