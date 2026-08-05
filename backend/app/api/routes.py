from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.services import generator
from backend.app.services.model_manager import model_manager
from backend.app.services.document_parser import parse_document
from backend.app.services.batch_generator import start_batch_job, get_job_status, submit_job_action
from backend.app.db.store import save_voice, list_voices, get_voice, delete_voice, search_voices, count_voices, get_stats, voices_store
from backend.app.services.generator import generate_audio_asset, generate_cloned_audio_asset
from backend.app.services.audio_processor import convert_audio_sync
from backend.app.services.model_selector import auto_select_model

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
    effects: dict = Field(default_factory=dict)
    smart_style: bool = Field(default=False)


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
    smart_style: bool = Field(default=False)

class MixClip(BaseModel):
    voice_id: str
    start_time_ms: int

class MixRequest(BaseModel):
    name: str = "Mixed Audio"
    clips: list[MixClip]
    output_format: str = "wav"


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/voice")
async def create_voice(payload: VoiceCreateRequest) -> dict[str, Any]:
    model_id = payload.model_id or auto_select_model(
        payload.text, payload.language, payload.style, model_manager
    )
    
    style_to_use = payload.style
    if payload.smart_style:
        from backend.app.services.semantic_analyzer import detect_style
        style_to_use = detect_style(payload.text)

    try:
        asset = generate_audio_asset(
            text=payload.text,
            voice_name=payload.voice_name,
            language=payload.language,
            style=style_to_use,
            model_id=model_id,
            voice_id=payload.voice_id,
            speed=payload.speed,
            pitch=payload.pitch,
            output_format="wav",
        )
        
        if payload.effects:
            from backend.app.services.audio_processor import apply_effects
            new_path = await apply_effects(Path(asset["file_path"]), payload.effects)
            asset["file_path"] = str(new_path)
            asset["file_size"] = new_path.stat().st_size
            
        if payload.output_format != "wav":
            new_path = convert_audio_sync(Path(asset["file_path"]), payload.output_format)
            asset["file_path"] = str(new_path)
            asset["file_size"] = new_path.stat().st_size
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    record = await save_voice(
        voice_name=payload.voice_name,
        language=payload.language,
        style=style_to_use,
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
            
        style_to_use = payload.style
        if payload.smart_style:
            from backend.app.services.semantic_analyzer import detect_style
            style_to_use = detect_style(text)
            
        try:
            asset = generate_audio_asset(
                text=text,
                voice_name=f"{payload.voice_name}_{i + 1:03d}",
                language=payload.language,
                style=style_to_use,
                model_id=model_id,
                voice_id=payload.voice_id,
                speed=payload.speed,
                pitch=payload.pitch,
                output_format="wav",
            )
            if payload.output_format != "wav":
                new_path = convert_audio_sync(Path(asset["file_path"]), payload.output_format)
                asset["file_path"] = str(new_path)
                asset["file_size"] = new_path.stat().st_size

            record = await save_voice(
                voice_name=f"{payload.voice_name}_{i + 1:03d}",
                language=payload.language,
                style=style_to_use,
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
    import tempfile
    import shutil

    # Preserve original extension so the engine receives the correct file type
    original_ext = Path(audio_file.filename or "audio.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(delete=False, suffix=original_ext) as tmp:
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

@router.get("/styles")
async def list_available_styles():
    from backend.app.services.voice_styles import list_styles
    return {"styles": list_styles()}


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
async def remove_voice(voice_id: str, background_tasks: BackgroundTasks) -> dict[str, str]:
    record = await get_voice(voice_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Voice not found")
    background_tasks.add_task(generator.delete_audio_file, record["file_path"])
    await voices_store.delete(voice_id)
    return {"status": "deleted", "id": voice_id}

@router.post("/voice/mix")
async def mix_audio_tracks(payload: MixRequest) -> dict[str, Any]:
    from backend.app.db.database import get_voice
    import uuid
    import time
    from pydub import AudioSegment
    import os

    try:
        if not payload.clips:
            raise HTTPException(status_code=400, detail="No clips provided")

        max_duration = 0
        loaded_clips = []
        for clip in payload.clips:
            voice_record = await get_voice(clip.voice_id)
            if not voice_record:
                continue
                
            file_path = AUDIO_DIR / voice_record["file_name"]
            if not file_path.exists():
                continue
                
            audio = AudioSegment.from_file(str(file_path))
            end_time = clip.start_time_ms + len(audio)
            if end_time > max_duration:
                max_duration = end_time
                
            loaded_clips.append({"audio": audio, "start": clip.start_time_ms})
            
        if not loaded_clips:
            raise HTTPException(status_code=400, detail="No valid clips found")

        # Create empty base track
        mixed = AudioSegment.silent(duration=max_duration)
        
        # Overlay clips
        for clip in loaded_clips:
            mixed = mixed.overlay(clip["audio"], position=clip["start"])
            
        # Export
        voice_id = str(uuid.uuid4())
        file_name = f"mix_{voice_id}.{payload.output_format}"
        file_path = AUDIO_DIR / file_name
        
        mixed.export(str(file_path), format=payload.output_format)
        
        # Save to DB
        from backend.app.db.database import save_voice
        record = await save_voice(
            voice_name=payload.name,
            language="mix",
            style="mix",
            text=f"Mixed audio from {len(loaded_clips)} tracks",
            model_id="mixer",
            voice_id="mixer",
            speed=1.0,
            pitch=0.0,
            file_name=file_name
        )
        return record
        
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Mixing failed: {str(exc)}")

@router.post("/voice/document")
async def create_voice_from_document(
    file: UploadFile = File(...),
    voice_name: str = Form("Document Audio"),
    language: str = Form("en"),
    style: str = Form("neutral"),
    speed: float = Form(1.0),
    pitch: float = Form(0.0),
    model_id: str = Form(None),
    voice_id: str = Form(None),
    chunking_strategy: str = Form("standard")
):
    # Enforce a 50 MB upload limit to prevent OOM on huge files
    MAX_BYTES = 50 * 1024 * 1024
    content = await file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB limit")
    try:
        text = parse_document(content, file.filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
        
    if not model_id or model_id in ("null", "undefined", "auto", "None", ""):
        model_id = auto_select_model(text[:500], language, style, model_manager)
        
    voice_settings = {
        "voice_name": voice_name,
        "language": language,
        "style": style,
        "speed": speed,
        "pitch": pitch,
        "model_id": model_id,
        "voice_id": voice_id,
        "chunking_strategy": chunking_strategy
    }
    
    # Needs absolute path to models/audio dir
    from backend.app.services.generator import AUDIO_DIR
    job_id = start_batch_job(text, voice_settings, str(AUDIO_DIR))
    
    return {"job_id": job_id, "status": "queued"}

@router.get("/voice/document/{job_id}/progress")
async def get_document_job_progress(job_id: str):
    status = get_job_status(job_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Job not found")
    return status

class JobAction(BaseModel):
    action: str # "skip", "cancel"

@router.post("/voice/document/{job_id}/action")
async def handle_document_job_action(job_id: str, payload: JobAction):
    submit_job_action(job_id, payload.action)
    return {"status": "action_submitted"}

class SceneRequest(BaseModel):
    script: str
    character_voices: dict
    settings: dict = Field(default_factory=dict)

@router.post("/voice/scene")
async def create_scene(payload: SceneRequest) -> dict[str, Any]:
    from backend.app.services.scene_generator import generate_scene
    try:
        result = await generate_scene(payload.script, payload.character_voices, payload.settings)
        
        record = await save_voice(
            voice_name="scene",
            language="en",
            style="neutral",
            text="[Scene Generated]",
            model_id="mixed",
            voice_id="mixed",
            speed=1.0,
            pitch=0.0,
            file_path=result["file_path"],
            file_size=Path(result["file_path"]).stat().st_size,
            duration_sec=None,
            output_format="wav",
        )
        return record
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

class RSSRequest(BaseModel):
    url: str
    voice_name: str = Field(default="RSS Audio")
    language: str = Field(default="en")
    style: str = Field(default="neutral")
    speed: float = Field(default=1.0)
    pitch: float = Field(default=0.0)
    model_id: str | None = None
    voice_id: str | None = None
    chunking_strategy: str = Field(default="standard")
    summarize_content: bool = Field(default=False)

@router.post("/voice/rss")
async def create_voice_from_rss(payload: RSSRequest) -> dict[str, Any]:
    from backend.app.services.rss_parser import fetch_rss_feed
    from backend.app.services.generator import AUDIO_DIR
    
    try:
        texts = fetch_rss_feed(payload.url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
        
    combined_text = "\n\n".join(texts)
    
    if payload.summarize_content:
        from backend.app.services.summarizer import summarize_text
        combined_text = summarize_text(combined_text)

    voice_settings = {
        "voice_name": payload.voice_name,
        "language": payload.language,
        "style": payload.style,
        "speed": payload.speed,
        "pitch": payload.pitch,
        "model_id": payload.model_id,
        "voice_id": payload.voice_id,
        "chunking_strategy": payload.chunking_strategy
    }
    
    job_id = start_batch_job(combined_text, voice_settings, str(AUDIO_DIR))
    
    return {"job_id": job_id, "status": "queued"}
