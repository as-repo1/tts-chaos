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
   - [backend/app/services/semantic_analyzer.py](../backend/app/services/semantic_analyzer.py)
   - [backend/app/services/summarizer.py](../backend/app/services/summarizer.py)
   - [backend/app/services/audio_processor.py](../backend/app/services/audio_processor.py)

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

