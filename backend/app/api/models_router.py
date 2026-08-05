from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.app.services.model_manager import model_manager, MODEL_CATALOG

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/catalog")
async def get_catalog():
    return {"models": model_manager.get_catalog()}

@router.get("/{model_id}/info")
async def get_model_info(model_id: str):
    info = next((m for m in MODEL_CATALOG if m.model_id == model_id), None)
    if info is None:
        raise HTTPException(status_code=404, detail="Unknown model")
    return {**info.__dict__, "is_installed": model_manager.is_installed(model_id)}


@router.get("/installed")
async def get_installed():
    installed = model_manager.list_installed()
    return {"models": [m.__dict__ for m in installed]}


@router.post("/download/{model_id}")
async def start_download(model_id: str):
    if model_manager.is_installed(model_id):
        raise HTTPException(status_code=409, detail="Model already installed")
    try:
        await model_manager.download(model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"status": "queued", "model_id": model_id}


@router.get("/download/{model_id}/progress")
async def download_progress(model_id: str):
    """SSE stream of download progress events."""
    queue = model_manager._progress.get(model_id)
    if queue is None:
        raise HTTPException(status_code=404, detail="No active download for this model")

    async def event_generator():
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {json.dumps(msg)}\n\n"
                if msg.get("event") in ("download_complete", "download_error"):
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                              headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.delete("/{model_id}")
async def delete_model(model_id: str):
    import shutil
    info = next((m for m in MODEL_CATALOG if m.model_id == model_id), None)
    if info is None:
        raise HTTPException(status_code=404, detail="Unknown model")
    if info.is_cloud:
        raise HTTPException(status_code=400, detail="Cannot delete cloud model")
    from backend.app.services.model_manager import MODELS_DIR
    model_dir = MODELS_DIR / info.engine / model_id
    if model_dir.exists():
        shutil.rmtree(model_dir)
    model_manager._engines.pop(model_id, None)
    return {"status": "deleted", "model_id": model_id}


@router.get("/{model_id}/voices")
async def list_model_voices(model_id: str):
    if not model_manager.is_installed(model_id):
        raise HTTPException(status_code=404, detail="Model not installed")
    engine = model_manager.get_engine(model_id)
    return {"voices": engine.list_voices(model_id=model_id)}


@router.get("/recommend")
async def recommend_model(text: str = "", language: str = "en", style: str = "neutral"):
    from backend.app.services.model_selector import auto_select_model
    model_id = auto_select_model(text, language, style, model_manager)
    return {"recommended_model_id": model_id}
