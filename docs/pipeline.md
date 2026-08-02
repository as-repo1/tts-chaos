# TTS Chaos — Pipeline

This document describes the full data flow and processing pipeline for every major operation.

---

## 1. Voice Generation Pipeline

```
User (Browser)
    │
    ▼
[POST /api/voice] ── VoiceCreateRequest
    │
    ├─► Validate payload (Pydantic)
    │
    ├─► Auto-select model (if model_id is null)
    │       │
    │       ├─ Query ModelManager.list_installed()
    │       ├─ Score each model (language match · style · quality)
    │       └─ Return best model_id
    │
    ├─► ModelManager.get_engine(model_id)
    │       │
    │       └─ Returns live TTSEngine instance
    │
    ├─► TTSEngine.generate(text, voice_id, speed, pitch)
    │       │
    │       ├─ [kokoro]    ONNX inference → raw PCM bytes
    │       ├─ [piper]     subprocess piper binary → WAV bytes
    │       ├─ [xtts]      PyTorch inference → WAV bytes
    │       └─ [edge-tts]  HTTPS to Microsoft → MP3/WAV bytes
    │
    ├─► generator.write_audio(bytes, format)
    │       │
    │       ├─ Write WAV to generated_audio/
    │       └─ Optionally encode to MP3 via ffmpeg subprocess
    │
    ├─► VoiceStore.save(record)
    │       │
    │       └─ INSERT INTO voices (SQLite, aiosqlite)
    │
    └─► Return VoiceRecord JSON to browser
```

---

## 2. Voice Cloning Pipeline (XTTS)

```
User (Browser)
    │
    ▼
[POST /api/voice/clone] ── (Multipart FormData: audio_file, text, voice_name)
    │
    ├─► Save uploaded audio to tempfile (.wav)
    │
    ├─► Call generator.generate_cloned_audio_asset(text, ref_audio_path, xtts-v2)
    │       │
    │       ├─ ModelManager.get_engine("xtts-v2")
    │       ├─ TTSEngine.generate_cloned()
    │       │       │
    │       │       └─ Coqui XTTS inference with gpt_cond_len=3, temperature=0.75
    │       │
    │       └─ Write output WAV to generated_audio/
    │
    ├─► Delete tempfile
    │
    ├─► VoiceStore.save(record) 
    │       │
    │       └─ INSERT INTO voices (model_id='xtts-v2', voice_id='cloned')
    │
    └─► Return VoiceRecord JSON to browser
```

---

## 2. Model Download Pipeline

```
User clicks "Download" on a model card
    │
    ▼
[POST /api/models/download/{model_id}]
    │
    ├─► Validate model_id exists in MODEL_CATALOG
    ├─► Check not already installed / downloading
    ├─► Create download record in model_downloads table (status=queued)
    └─► Spawn asyncio background task
            │
            ▼
    BackgroundTask: model_manager.download(model_id)
            │
            ├─► Resolve download source
            │       ├─ HuggingFace Hub: huggingface_hub.hf_hub_download()
            │       └─ Direct URL: httpx streaming GET
            │
            ├─► Stream file in chunks (8192 bytes)
            │       │
            │       ├─ Write chunk to models/{engine}/{model_id}/
            │       ├─ Update progress = bytes_received / total_bytes
            │       └─ Publish progress to asyncio.Queue
            │
            ├─► Verify checksum (SHA256 if available)
            │
            ├─► Initialize engine (load model into memory)
            │       ├─ [kokoro]  ort.InferenceSession(model.onnx)
            │       ├─ [piper]   check binary + model.onnx present
            │       ├─ [xtts]    TTS(model_name).to(device)
            │       └─ [edge]    no-op (cloud, always available)
            │
            └─► UPDATE model_downloads SET status='complete'


Parallel: Browser polls progress
    │
    ▼
[GET /api/models/download/{model_id}/progress]  ← SSE endpoint
    │
    └─► EventSourceResponse — reads from asyncio.Queue
            │
            ├─ event: download_started  { model_id, total_bytes }
            ├─ event: download_progress { model_id, progress: 0.0–1.0, mb_received }
            ├─ event: download_complete { model_id }
            └─ event: download_error    { model_id, error }
```

---

## 3. Model Auto-Selection Pipeline

```
VoiceCreateRequest { model_id: null, language: "fr", style: "dramatic" }
    │
    ▼
model_selector.auto_select(text, language, style)
    │
    ├─► Build candidate list from ModelManager.list_installed()
    │
    ├─► Score each candidate:
    │       score = 0
    │       if language in model.languages:     score += 50
    │       if style in model.supported_styles: score += 20
    │       score += model.quality_score         (0–30)
    │       if model.is_gpu and cuda_available:  score += 10
    │
    ├─► Sort by score descending
    │
    ├─► Pick top candidate
    │
    ├─► If no installed model matches → fallback to edge-tts
    │
    └─► Return model_id string
```

---

## 4. Audio Streaming Pipeline

```
User clicks ▶ Play in the Library
    │
    ▼
Browser: new Audio(src="/api/voices/{id}/audio")
    │
    ▼
[GET /api/voices/{id}/audio]
    │
    ├─► Lookup voice record in SQLite
    ├─► Resolve file_path on disk
    ├─► Read Range header (if present)
    └─► FileResponse with:
            Content-Type: audio/wav (or audio/mpeg)
            Accept-Ranges: bytes
            Content-Range: bytes start-end/total  (if range)
```

---

## 5. Frontend Rendering Pipeline

```
Browser loads /
    │
    ▼
index.html parsed → app.js (ES modules) loaded
    │
    ├─► api.getModels()      → populate Models tab
    ├─► api.getVoices()      → populate Library tab
    └─► api.getRecommendation() → show auto-select hint in Studio
            │
            ▼
    User navigates tabs (no page reload — CSS class switching)
            │
    Studio tab:
    ├─► User types text → debounced recommendation refresh
    ├─► User selects model → voice dropdown updates via api.getModelVoices()
    └─► Submit → showWaveformAnimation() → POST /api/voice → appendVoiceCard()

    Models tab:
    ├─► Cards render with badges: [Cloud] [Installed] [Downloading X%]
    └─► Download click → EventSource(progressURL) → update progress ring

    Library tab:
    ├─► Voice cards with inline <audio> + custom waveform via Web Audio API
    └─► Delete click → DELETE /api/voices/{id} → remove card

    Cloning tab:
    ├─► Drag-and-drop audio file upload
    └─► Submit → Show multi-bar waveform → POST /api/voice/clone (FormData) → Redirect to Library
```

---

## 6. Startup Pipeline

```
uvicorn starts
    │
    ▼
FastAPI lifespan (async context manager)
    │
    ├─► aiosqlite: create/migrate voices.db
    │       CREATE TABLE IF NOT EXISTS voices (...)
    │
    ├─► ModelManager.scan_installed()
    │       for engine_dir in models/:
    │           check if model files present → mark as installed
    │
    ├─► Register routers
    │       /api/voice, /api/voices → routes.py
    │       /api/models/*           → models_router.py
    │
    ├─► Mount /static → frontend/static/
    └─► Mount / → frontend/index.html (SPA catch-all)
```

---

## 7. Docker Deployment Pipeline

```
Host OS
    │
    ▼
[docker-compose up -d]
    │
    ├─► Builds image from Dockerfile (python:3.11-slim)
    │       ├─ Install ffmpeg, build-essential
    │       └─ uv pip install requirements
    │
    ├─► Mounts Volumes: ./models, ./generated_audio
    │
    └─► Exposes Container Port 2002 -> Host Port 2002
```

---

## 7. Database Schema

```sql
-- Generated voice records
CREATE TABLE voices (
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
```

---

## 8. Error Handling Matrix

| Scenario | HTTP Code | Client Action |
|---|---|---|
| Model not installed, no fallback | 503 | Show "No model available" toast |
| Model download fails (network) | 200 (SSE error event) | Show retry button |
| Text too long (>5000 chars) | 422 | Highlight textarea, show limit |
| Audio file missing on disk | 404 | Show "regenerate" prompt |
| Engine crash during generation | 500 | Show error toast + log |
| Concurrent generation limit hit | 429 | Queue indicator in UI |
