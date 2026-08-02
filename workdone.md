# TTS Chaos — Work Done Log

Tracks everything completed, what's in progress, and what's pending.
Updated as work progresses. Entries are timestamped and grouped by session.

---

## Status Legend

| Symbol | Meaning |
|---|---|
| ✅ | Completed and verified |
| 🔧 | Exists but is a stub / placeholder |
| 📄 | Documentation only (no code yet) |
| ⏳ | Queued — next to be implemented |
| ❌ | Not started |

---

## Session 1 — 2026-08-03 · Planning & Scaffolding

### ✅ Project scaffolded (initial skeleton)

The initial project skeleton was committed to git before this session began.
All source files below are **stubs** — they exist but do not perform real TTS.

| File | Lines | Status | Notes |
|---|---|---|---|
| `backend/app/main.py` | 18 | 🔧 Stub | FastAPI app, mounts /static, serves index.html. No lifespan, no DB init. |
| `backend/app/api/routes.py` | 88 | 🔧 Stub | Voice CRUD. Auto-select always returns `"local-tts"`. No delete, no audio stream. |
| `backend/app/services/generator.py` | 47 | 🔧 Stub | Generates a **sine-wave WAV** — not real TTS. |
| `backend/app/services/model_selector.py` | 19 | 🔧 Stub | Always returns `"local-tts"` regardless of input. |
| `backend/app/db/store.py` | 52 | 🔧 Stub | JSON flat-file store (`voices.json`). No async, no delete, no pagination. |
| `frontend/index.html` | 54 | 🔧 Stub | Basic form: voice name, language, style, model select, textarea. |
| `frontend/static/app.js` | 56 | 🔧 Stub | Fetches /models, /voices, POSTs /voice. Uses `alert()` for feedback. |
| `frontend/static/app.css` | 52 | 🔧 Stub | Minimal dark theme. No glassmorphism, no animations, no layout. |

**What the stub does today:**
- Starts with `uvicorn backend.app.main:app --reload`
- Loads model list (hardcoded 3 entries)
- Accepts text form submission
- Writes a fake sine-wave `.wav` to `generated_audio/`
- Saves record to `voices.json`
- Shows a download link

**What it does NOT do:**
- Real TTS synthesis
- Model download from HuggingFace or any source
- Real model selection logic
- Inline audio playback
- Progress indicators
- SQLite persistence
- Delete / manage voices

---

### ✅ Documentation written

Full planning documentation authored and saved to the project root.

| File | Size | Contents |
|---|---|---|
| [`README.md`](./README.md) | 5.8 KB | Project overview, quick start, API reference, model comparison table, config reference, roadmap |
| [`pipeline.md`](./pipeline.md) | 7.8 KB | 8 ASCII data-flow diagrams: voice generation, model download, auto-selection scoring, audio streaming, frontend rendering, startup sequence, DB schema, error matrix |
| [`implementation.md`](./implementation.md) | 32 KB | Step-by-step dev guide for all 4 phases: every file change with full code, in execution order |

---

## ✅ Phase 1: Real Engine Layer

### ✅ Step 1.1 — `pyproject.toml`
- Create with proper dependency groups: `kokoro`, `piper`, `xtts`, `edge`, `audio`, `all`
- Replaces ad-hoc pip installs
- **Blocker for everything else**

### ✅ Step 1.2 — `backend/app/services/engines/base.py`
- Abstract `TTSEngine` class: `is_available()`, `generate()`, `list_voices()`
- Required by all engine implementations

### ✅ Step 1.3 — `backend/app/services/engines/edge_tts_engine.py`
- Wraps `edge-tts` Microsoft cloud API
- No model download needed — instant validation
- First real audio output end-to-end

### ✅ Step 1.4 — `backend/app/services/engines/kokoro.py`
- ONNX inference via `kokoro-onnx`
- Voices: af_heart, af_sky, am_adam, am_michael, bf_emma, bm_lewis
- Requires `kokoro-v1.0.onnx` + `voices.bin` in `models/kokoro/`

### ✅ Step 1.5 — `backend/app/services/engines/piper.py`
- Wraps `piper-tts` Python library
- Scans `models/piper/` for installed `.onnx` voice files

### ✅ Step 1.6 — `backend/app/services/model_selector.py` (rewrite)
- Scoring algorithm: language match (50pts) + style match (20pts) + quality score (0–30pts)
- Falls back to `edge-tts` if nothing installed

### ✅ Step 1.7 — `backend/app/services/model_manager.py` (new)
- `MODEL_CATALOG` with 4 entries (edge-tts, kokoro-82m, piper-en-lessac + more)
- `ModelManager` class: `get_catalog()`, `list_installed()`, `is_installed()`, `download()`, `get_engine()`
- `_stream_file()` async HuggingFace/URL downloader with progress queue

### ✅ Step 1.8 — `backend/app/services/generator.py` (rewrite)
- Dispatches to real engine via `model_manager.get_engine(model_id).generate(...)`
- Removes sine-wave stub

---

## ✅ Phase 2: Model Management API

### ✅ Step 2.1 — `backend/app/db/store.py` (rewrite)
- Replace JSON file with SQLite via `aiosqlite`
- Tables: `voices`, `model_downloads`
- Async CRUD: `save_voice`, `list_voices`, `get_voice`, `delete_voice`

### ✅ Step 2.2 — `backend/app/api/models_router.py` (new)
- `GET /api/models/catalog` — full catalog with install status
- `GET /api/models/installed`
- `POST /api/models/download/{model_id}` — starts background download
- `GET /api/models/download/{model_id}/progress` — SSE stream
- `DELETE /api/models/{model_id}`
- `GET /api/models/{model_id}/voices`
- `GET /api/models/recommend`

### ✅ Step 2.3 — `backend/app/api/routes.py` (rewrite)
- Add `/api` prefix
- Enhanced `VoiceCreateRequest` with `speed`, `pitch`, `voice_id`, `output_format`
- `DELETE /api/voices/{id}`
- `GET /api/voices/{id}/audio` — range-request aware `FileResponse`

### ✅ Step 2.4 — `backend/app/main.py` (rewrite)
- Add `lifespan` context manager
- Call `init_db()` on startup
- Include both `voice_router` and `models_router`

---

## ✅ Phase 3: Premium Frontend

### ✅ Step 3.1 — `frontend/static/app.css` (full redesign)
- Design tokens: `#080b14` base, `#7c3aed` accent, `#06b6d4` highlight
- Components: `.sidebar`, `.model-card`, `.progress-ring`, `.waveform`, `.voice-card`, `.toast`
- Inter font from Google Fonts
- Glassmorphism cards with `backdrop-filter: blur(20px)`
- CSS keyframe animations

### ✅ Step 3.2 — `frontend/index.html` (full redesign)
- 3-tab SPA: Studio · Models · Library
- Semantic HTML5
- SEO meta tags

### ✅ Step 3.3 — `frontend/static/app.js` (full rewrite)
- Modular sections: API, Studio, Models, Library, Toast, Tab Router
- SSE EventSource for download progress
- Web Audio API waveform visualizer
- Inline `<audio>` player with custom UI

---

## Pending Work — Phase 4: Polish

### ❌ Settings panel (4th sidebar tab)
### ❌ Batch generation (`POST /api/voices/batch`)
### ❌ Voice cloning support (XTTS reference audio)
### ❌ `pyproject.toml` script entry: `tts-chaos = "backend.app.main:app"`
### ❌ `Dockerfile` + `docker-compose.yml`

---

## Summary Counters

| Category | Count |
|---|---|
| Files existing (stubs) | 8 |
| Documentation files written | 3 |
| Engine implementations done | 0 / 4 |
| API endpoints implemented (real) | 0 / 12 |
| Frontend phases complete | 0 / 3 |
| **Overall progress** | **~10%** |

---

*Last updated: 2026-08-03 · Session 1 end*
