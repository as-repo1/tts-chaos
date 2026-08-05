# TTS Chaos — Implementation Notes

This guide exists to explain the repository’s engineering shape in practical, maintainer-friendly terms. It is the “how do I reason about this codebase?” document.

---

## 1. Current runtime architecture

The application is organized around four major layers:

1. API layer
   - [backend/app/api/routes.py](../backend/app/api/routes.py)
   - [backend/app/api/models_router.py](../backend/app/api/models_router.py)

2. Service layer
   - [backend/app/services/generator.py](../backend/app/services/generator.py)
   - [backend/app/services/model_manager.py](../backend/app/services/model_manager.py)
   - [backend/app/services/model_selector.py](../backend/app/services/model_selector.py)
   - [backend/app/services/batch_generator.py](../backend/app/services/batch_generator.py)

3. Persistence layer
   - [backend/app/db/store.py](../backend/app/db/store.py)

4. Frontend shell
   - [frontend/index.html](../frontend/index.html)
   - [frontend/static/app.js](../frontend/static/app.js)
   - [frontend/static/app.css](../frontend/static/app.css)

---

## 2. Relevant runtime entrypoints

### FastAPI app bootstrap

The main app object is created in [backend/app/main.py](../backend/app/main.py). This file is the best place to understand:

- startup and shutdown lifecycle
- middleware config
- static file mounts
- health and system info endpoints
- environment-dependent runtime defaults

### Health and status endpoints

The route layer explicitly exposes:

- `GET /api/health`
- `GET /api/system/info`

This is the fastest verification path when the backend is running in any environment.

---

## 3. Engine model

The engine abstraction is implemented under [backend/app/services/engines](../backend/app/services/engines):

- `base.py` defines the common contract
- `edge_tts_engine.py` gives the cloud fallback interface
- `kokoro.py` gives the local ONNX-oriented path
- `piper.py` handles local Piper model loading patterns
- `xtts_engine.py` provides the higher-cost cloning-oriented branch

The selection and runtime suitability checks are centralized through [backend/app/services/model_manager.py](../backend/app/services/model_manager.py).

---

## 4. Persistence behavior

Voice records are stored in SQLite, with metadata written by the async DB helper functions in [backend/app/db/store.py](../backend/app/db/store.py).

The schema is intentionally small and records the minimal shape needed to recover the audio asset and its metadata later:

- `voice_name`
- `language`
- `style`
- `text`
- `model_id`
- `voice_id`
- `speed`
- `pitch`
- `file_path`
- `file_size`
- `duration_sec`
- `output_format`
- `created_at`

The route layer and batch layer both assume this persistence contract, so any future refactor should preserve it.

---

## 5. Document and batch processing notes

The document-to-audio workflow is routed through:

- [backend/app/api/routes.py](../backend/app/api/routes.py)
- [backend/app/services/batch_generator.py](../backend/app/services/batch_generator.py)
- [backend/app/services/document_parser.py](../backend/app/services/document_parser.py)

This path currently behaves as a job-queue style MVP:

1. parse content
2. chunk it into smaller text spans
3. synthesize each chunk
4. merge the output with `ffmpeg`
5. save the final merged audio asset
6. write a record to the voice library

This is the most operationally sensitive part of the app and should be treated as such during future maintenance.

---

## 6. Deployment shape

The repo now supports two practical deployment modes:

### Local Python runtime

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn backend.app.main:app --host 0.0.0.0 --port 2002
```

### Docker runtime

```bash
docker compose up --build -d
```

The Docker deployment is the preferred self-hosted baseline.

---

## 7. Production-readiness notes

The current production pass has already improved the repo by making the startup surface more deterministic:

- environment variables now control runtime exposure
- the container no longer depends on a missing `requirements.txt`
- the FastAPI app has a safer origin posture by default
- startup-time imports are now compatible with the expected persistence interface

Those are the kinds of changes that matter the most when the project is handed to a future maintainer or operator.

---

## 8. Maintainer checklist

If you are debugging a future issue, read in this order:

1. [backend/app/main.py](../backend/app/main.py)
2. [backend/app/api/routes.py](../backend/app/api/routes.py)
3. [backend/app/api/models_router.py](../backend/app/api/models_router.py)
4. [backend/app/db/store.py](../backend/app/db/store.py)
5. [backend/app/services/model_manager.py](../backend/app/services/model_manager.py)
6. [backend/app/services/batch_generator.py](../backend/app/services/batch_generator.py)

That reading order gives a reliable “startup → route → storage → model discovery → background task” mental model.

---

## 9. Known limitations worth preserving in memory

- `edge-tts` depends on the optional package installation being present.
- Local models are not automatically validated beyond the manager’s availability checks.
- Batch jobs are background tasks and should not be treated as a fully durable long-running service without a stronger job store.
- UI state and runtime preferences are still limited compared to a full operational admin panel.

These are the main follow-up areas for the next engineering pass.

        voices = []
        for onnx in MODELS_DIR.glob("**/*.onnx"):
            lang = onnx.parent.name.split("_")[0]
            voices.append({"id": onnx.stem, "name": onnx.stem.replace("-", " ").title(),
                           "gender": "N", "language": lang})
        return voices
```

---

### Step 1.6 — Update Model Selector

**File:** `backend/app/services/model_selector.py` ← REPLACE ENTIRELY

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model_manager import ModelManager


def auto_select_model(
    text: str,
    language: str,
    style: str,
    model_manager: "ModelManager",
) -> str:
    """Score installed models and return the best model_id."""
    candidates = model_manager.list_installed()

    if not candidates:
        # Edge-TTS is always available as cloud fallback
        return "edge-tts"

    scores: list[tuple[int, str]] = []
    for m in candidates:
        score = 0
        # Language match
        if language in m.languages or language.split("-")[0] in m.languages:
            score += 50
        # Style support
        if style in m.supported_styles:
            score += 20
        # Intrinsic quality
        score += m.quality_score
        scores.append((score, m.model_id))

    scores.sort(key=lambda t: t[0], reverse=True)
    return scores[0][1]
```

---

### Step 1.7 — Create Model Manager Service

**File:** `backend/app/services/model_manager.py` ← CREATE NEW

```python
from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class ModelInfo:
    model_id: str
    display_name: str
    engine: str              # "kokoro" | "piper" | "xtts" | "edge-tts"
    description: str
    size_mb: int
    languages: list[str]
    supported_styles: list[str]
    quality_score: int
    hf_repo: str | None = None
    hf_filename: str | None = None
    download_url: str | None = None
    is_cloud: bool = False   # no download needed
    extra_files: list[tuple[str, str]] = field(default_factory=list)  # [(url, dest_name)]


# ── Catalog of all known downloadable models ──────────────────────────────────

MODEL_CATALOG: list[ModelInfo] = [
    ModelInfo(
        model_id="edge-tts",
        display_name="Edge TTS (Cloud)",
        engine="edge-tts",
        description="Microsoft Azure TTS — 400+ voices, 60+ languages. No download needed.",
        size_mb=0,
        languages=["en","fr","de","es","ja","zh","ar","pt","it","ko","nl","pl","ru","sv","tr"],
        supported_styles=["neutral","cheerful","sad","angry"],
        quality_score=70,
        is_cloud=True,
    ),
    ModelInfo(
        model_id="kokoro-82m",
        display_name="Kokoro 82M",
        engine="kokoro",
        description="Lightweight ONNX model. State-of-the-art English TTS at only 82M parameters.",
        size_mb=350,
        languages=["en"],
        supported_styles=["neutral","soft","dramatic"],
        quality_score=88,
        hf_repo="hexgrad/Kokoro-82M",
        hf_filename="kokoro-v1.0.onnx",
        extra_files=[
            ("https://huggingface.co/hexgrad/Kokoro-82M/resolve/main/voices.bin", "voices.bin"),
        ],
    ),
    ModelInfo(
        model_id="piper-en-lessac",
        display_name="Piper EN Lessac",
        engine="piper",
        description="Piper TTS — fast CPU inference, American English (Lessac voice).",
        size_mb=63,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=75,
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
             "en_US-lessac-medium.onnx.json"),
        ],
    ),
]


class ModelManager:
    def __init__(self):
        self._engines: dict[str, object] = {}  # model_id → TTSEngine instance
        self._progress: dict[str, asyncio.Queue] = {}
        self._scan_installed()

    # ── Catalog ───────────────────────────────────────────────────────────────

    def get_catalog(self) -> list[dict]:
        return [
            {**m.__dict__, "is_installed": self.is_installed(m.model_id),
             "is_downloading": m.model_id in self._progress}
            for m in MODEL_CATALOG
        ]

    def list_installed(self) -> list[ModelInfo]:
        return [m for m in MODEL_CATALOG if self.is_installed(m.model_id)]

    def is_installed(self, model_id: str) -> bool:
        if model_id == "edge-tts":
            try:
                import edge_tts  # noqa: F401
                return True
            except ImportError:
                return False
        engine = self._engines.get(model_id)
        return engine is not None and engine.is_available()

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(self, model_id: str) -> asyncio.Queue:
        """Start background download. Returns a progress Queue."""
        info = self._find_info(model_id)
        if info is None:
            raise ValueError(f"Unknown model: {model_id}")

        queue: asyncio.Queue = asyncio.Queue()
        self._progress[model_id] = queue

        async def _download_task():
            try:
                dest_dir = MODELS_DIR / info.engine / model_id
                dest_dir.mkdir(parents=True, exist_ok=True)

                files_to_download = []
                if info.download_url:
                    files_to_download.append((info.download_url, info.hf_filename or "model.onnx"))
                elif info.hf_repo and info.hf_filename:
                    url = f"https://huggingface.co/{info.hf_repo}/resolve/main/{info.hf_filename}"
                    files_to_download.append((url, info.hf_filename))
                for url, name in (info.extra_files or []):
                    files_to_download.append((url, name))

                for url, dest_name in files_to_download:
                    await queue.put({"event": "download_started", "file": dest_name})
                    await _stream_file(url, dest_dir / dest_name, queue, model_id)

                await queue.put({"event": "download_complete", "model_id": model_id})
                self._scan_installed()
            except Exception as exc:
                await queue.put({"event": "download_error", "error": str(exc)})
            finally:
                self._progress.pop(model_id, None)

        asyncio.create_task(_download_task())
        return queue

    # ── Engine access ─────────────────────────────────────────────────────────

    def get_engine(self, model_id: str):
        if model_id not in self._engines:
            self._load_engine(model_id)
        return self._engines[model_id]

    # ── Private helpers ───────────────────────────────────────────────────────

    def _scan_installed(self):
        """Load engine instances for all installed models."""
        from .engines.edge_tts_engine import EdgeTTSEngine
        from .engines.kokoro import KokoroEngine
        from .engines.piper import PiperEngine

        engine_map = {
            "edge-tts": EdgeTTSEngine,
            "kokoro-82m": KokoroEngine,
            "piper-en-lessac": PiperEngine,
        }
        for model_id, cls in engine_map.items():
            inst = cls()
            if inst.is_available():
                self._engines[model_id] = inst

    def _load_engine(self, model_id: str):
        self._scan_installed()

    def _find_info(self, model_id: str) -> ModelInfo | None:
        return next((m for m in MODEL_CATALOG if m.model_id == model_id), None)


async def _stream_file(url: str, dest: Path, queue: asyncio.Queue, model_id: str):
    async with httpx.AsyncClient(follow_redirects=True, timeout=300) as client:
        async with client.stream("GET", url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            received = 0
            with open(dest, "wb") as f:
                async for chunk in resp.aiter_bytes(8192):
                    f.write(chunk)
                    received += len(chunk)
                    progress = received / total if total else 0
                    await queue.put({
                        "event": "download_progress",
                        "model_id": model_id,
                        "progress": round(progress, 3),
                        "mb_received": round(received / 1_048_576, 1),
                        "mb_total": round(total / 1_048_576, 1),
                    })


model_manager = ModelManager()
```

---

### Step 1.8 — Update Generator

**File:** `backend/app/services/generator.py` ← REPLACE ENTIRELY

```python
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
```

---

## PHASE 2 — Model Management API & DB Upgrade

### Step 2.1 — Upgrade Database Store

**File:** `backend/app/db/store.py` ← REPLACE ENTIRELY

```python
from __future__ import annotations

import aiosqlite
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from typing import Any

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "voices.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CREATE_VOICES = """
CREATE TABLE IF NOT EXISTS voices (
    id              TEXT PRIMARY KEY,
    voice_name      TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    style           TEXT NOT NULL DEFAULT 'neutral',
    text            TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    voice_id        TEXT,
    speed           REAL NOT NULL DEFAULT 1.0,
    pitch           REAL NOT NULL DEFAULT 0.0,
    file_path       TEXT NOT NULL,
    file_size       INTEGER,
    duration_sec    REAL,
    output_format   TEXT NOT NULL DEFAULT 'wav',
    created_at      TEXT NOT NULL
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_VOICES)
        await db.commit()

async def save_voice(**kwargs) -> dict[str, Any]:
    record = {
        "id": str(uuid4()),
        "created_at": datetime.utcnow().isoformat(),
        **kwargs,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO voices VALUES (:id,:voice_name,:language,:style,:text,:model_id,"
            ":voice_id,:speed,:pitch,:file_path,:file_size,:duration_sec,:output_format,:created_at)",
            record,
        )
        await db.commit()
    return record

async def list_voices(offset: int = 0, limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM voices ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def get_voice(voice_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM voices WHERE id=?", (voice_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

async def delete_voice(voice_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM voices WHERE id=?", (voice_id,))
        await db.commit()
        return cur.rowcount > 0
```

---

### Step 2.2 — Create Models Router

**File:** `backend/app/api/models_router.py` ← CREATE NEW

```python
from __future__ import annotations

import asyncio
import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from backend.app.services.model_manager import model_manager

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/catalog")
async def get_catalog():
    return {"models": model_manager.get_catalog()}


@router.get("/installed")
async def get_installed():
    installed = model_manager.list_installed()
    return {"models": [m.__dict__ for m in installed]}


@router.post("/download/{model_id}")
async def start_download(model_id: str):
    if model_manager.is_installed(model_id):
        raise HTTPException(status_code=409, detail="Model already installed")
    await model_manager.download(model_id)
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
    from pathlib import Path
    info = next((m for m in model_manager.MODEL_CATALOG if m.model_id == model_id), None)
    if info is None:
        raise HTTPException(status_code=404, detail="Unknown model")
    if info.is_cloud:
        raise HTTPException(status_code=400, detail="Cannot delete cloud model")
    model_dir = Path("models") / info.engine / model_id
    if model_dir.exists():
        shutil.rmtree(model_dir)
    model_manager._engines.pop(model_id, None)
    return {"status": "deleted", "model_id": model_id}


@router.get("/{model_id}/voices")
async def list_model_voices(model_id: str):
    if not model_manager.is_installed(model_id):
        raise HTTPException(status_code=404, detail="Model not installed")
    engine = model_manager.get_engine(model_id)
    return {"voices": engine.list_voices()}


@router.get("/recommend")
async def recommend_model(text: str = "", language: str = "en", style: str = "neutral"):
    from backend.app.services.model_selector import auto_select_model
    model_id = auto_select_model(text, language, style, model_manager)
    return {"recommended_model_id": model_id}
```

---

### Step 2.3 — Update Voice Router

**File:** `backend/app/api/routes.py` ← REPLACE ENTIRELY

```python
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
```

---

### Step 2.4 — Update main.py

**File:** `backend/app/main.py` ← REPLACE ENTIRELY

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router as voice_router
from backend.app.api.models_router import router as models_router
from backend.app.db.store import init_db

APP_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = APP_ROOT / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="TTS Chaos", version="1.0.0", lifespan=lifespan)
app.include_router(voice_router)
app.include_router(models_router)

app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    return HTMLResponse((FRONTEND_DIR / "index.html").read_text())
```

---

## PHASE 3 — Premium Frontend

### Step 3.1 — Redesign app.css

**File:** `frontend/static/app.css` ← REPLACE ENTIRELY

Key design decisions:
- Background: `#080b14` (deep space black)
- Accent: `#7c3aed` (electric violet) + `#06b6d4` (neon cyan)
- Cards: `rgba(255,255,255,0.04)` background + `backdrop-filter: blur(20px)`
- Font: Inter from Google Fonts
- Progress ring: SVG `stroke-dasharray` animation
- Waveform bars: CSS keyframe stagger animation

Full implementation covers:
- `.sidebar` with icon + label navigation tabs
- `.model-card` with `.badge` (cloud/installed/downloading)
- `.progress-ring` SVG component
- `.voice-form` studio layout
- `.waveform` animated equalizer bars
- `.voice-card` library entry with inline player
- `.toast-container` notification system

---

### Step 3.2 — Redesign index.html

**File:** `frontend/index.html` ← REPLACE ENTIRELY

Three-tab SPA layout:
```html
<body>
  <aside class="sidebar">         ← Tab navigation
  <main>
    <section id="tab-studio">     ← Voice creation form
    <section id="tab-models">     ← Model browser grid
    <section id="tab-library">    ← Generated voices list
  </main>
</body>
```

---

### Step 3.3 — Rewrite app.js

**File:** `frontend/static/app.js` ← REPLACE ENTIRELY

Structured as immediately-invoked modules:

```
app.js
├── TAB ROUTER          switchTab(tabName)
├── API MODULE          api.{getModels, getVoices, createVoice, downloadModel, deleteVoice}
├── STUDIO MODULE       handleVoiceForm(), updateRecommendation(), showWaveform()
├── MODELS MODULE       renderModelCards(), startDownload(), trackProgress(SSE)
├── LIBRARY MODULE      renderVoiceCards(), initPlayer(), deleteVoice()
└── TOAST MODULE        toast.show(message, type)
```

---

## PHASE 4 — Polish & Extras

### Step 4.1 — Settings Panel
- Add `GET /api/settings` and `POST /api/settings`
- Store settings in `backend/app/data/settings.json`
- UI: 4th sidebar tab with toggle/select inputs

### Step 4.2 — Batch Generation
- New endpoint: `POST /api/voices/batch` — accepts `texts: list[str]`
- Runs generations concurrently with `asyncio.gather`
- Frontend: textarea split by newline, progress per item

### Step 4.3 — Voice Clone Support (XTTS)
- `POST /api/voices/clone` — multipart form: `text + reference_audio`
- Save reference audio to `models/xtts/references/`
- Pass file path to XTTS engine

---

## Verification Checklist

After each phase, run these checks:

```bash
# Phase 1
python -c "from backend.app.services.engines.edge_tts_engine import EdgeTTSEngine; e=EdgeTTSEngine(); print(e.is_available())"

# Phase 2
uvicorn backend.app.main:app --reload
curl http://localhost:8000/api/models/catalog | python -m json.tool
curl http://localhost:8000/api/models/recommend?language=en

# Phase 3 (in browser)
# Open http://localhost:8000
# Check: 3 tabs visible, Models tab shows catalog, Studio shows form
# Download Edge-TTS → progress shown → badge changes to "Installed"
# Create voice → waveform animation → voice appears in Library
# Play voice → inline audio player works
# Delete voice → card removed
```
