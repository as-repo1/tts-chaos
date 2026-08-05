# 🎙️ TTS Chaos — AI Voice Studio

TTS Chaos is a self-hosted, browser-first text-to-speech studio built with FastAPI and vanilla HTML/CSS/JS. It exposes a small REST API, a model catalog and download workflow, a SQLite-backed voice library, and a hybrid runtime that can use cloud voices (Edge-TTS) or locally installed models.

---

## ✨ What this repo does

- Generates audio from text using a pluggable engine abstraction
- Supports cloud fallback with Edge-TTS and local engines for Kokoro, Piper, and XTTS
- Lets users browse model availability, download progress, and recommended model selection
- Persists voice records in SQLite and streams saved audio files back to the browser
- Ships with a Docker-first deployment shape for self-hosting

---

## 🗂️ Current project structure

```text
tts-chaos/
├── README.md
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── backend/
│   └── app/
│       ├── main.py
│       ├── api/
│       │   ├── routes.py
│       │   └── models_router.py
│       ├── db/
│       │   └── store.py
│       └── services/
│           ├── batch_generator.py
│           ├── document_parser.py
│           ├── generator.py
│           ├── model_manager.py
│           ├── model_selector.py
│           └── engines/
│               ├── base.py
│               ├── edge_tts_engine.py
│               ├── kokoro.py
│               ├── piper.py
│               └── xtts_engine.py
├── frontend/
│   ├── index.html
│   └── static/
│       ├── app.css
│       └── app.js
├── docs/
│   ├── implementation.md
│   ├── pipeline.md
│   └── workdone.md
├── models/
├── generated_audio/
└── backend/app/data/voices.db
```

---

## 🚀 Quick start

### 1. Prerequisites

- Python 3.11+
- `pip` or `uv`
- `ffmpeg` for document/media processing and audio composition
- Optional: GPU-enabled Python environment for heavier XTTS work

### 2. Install and run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn backend.app.main:app --host 0.0.0.0 --port 2002
```

### 3. Run with Docker

```bash
docker compose up --build -d
```

Then open the app at `http://localhost:2002`.

### 4. Environment variables

The runtime now reads the following defaults from the environment:

```env
HOST=0.0.0.0
PORT=2002
ENABLE_DOCS=false
CORS_ORIGINS=http://localhost:2002,http://127.0.0.1:2002
```

This keeps the app self-hosting friendly and avoids overexposing the API stack.

---

## 🔌 Current API surface

Base URL: `http://localhost:2002`

### Health and system

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Simple health probe |
| `GET` | `/api/system/info` | Runtime metadata, installed model IDs, disk usage |

### Voice generation and library

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/voice` | Generate a single voice |
| `POST` | `/api/voice/batch` | Batch voice generation from a list of texts |
| `POST` | `/api/voice/clone` | Clone a voice from uploaded reference audio |
| `POST` | `/api/voice/document` | Queue a document-to-audio batch job |
| `GET` | `/api/voices` | List stored voices |
| `GET` | `/api/voices/search` | Search stored voices |
| `GET` | `/api/voices/stats` | Inventory and storage statistics |
| `GET` | `/api/voices/{voice_id}/audio` | Stream saved audio |
| `DELETE` | `/api/voices/{voice_id}` | Remove a stored voice record |
| `GET` | `/api/voice/document/{job_id}/progress` | Poll a document job status |
| `POST` | `/api/voice/document/{job_id}/action` | Skip/cancel a document job |

### Model catalog operations

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/models/catalog` | Full model catalog |
| `GET` | `/api/models/installed` | Installed models only |
| `POST` | `/api/models/download/{model_id}` | Start a model download job |
| `GET` | `/api/models/download/{model_id}/progress` | SSE progress stream |
| `DELETE` | `/api/models/{model_id}` | Delete an installed local model |
| `GET` | `/api/models/{model_id}/voices` | List engine voices |
| `GET` | `/api/models/recommend` | Recommend a model from the installed set |

---

## 🤖 Current model posture

- `edge-tts` is the cloud fallback and is treated as always available if the optional dependency is present.
- `kokoro-82m`, `piper-*`, and `xtts-v2` are model-catalog based and are instantiated only when their runtime requirements exist.
- Model download progress is streamed through a queue-backed SSE endpoint.
- Disk usage is surfaced through the system info route.

---

## ⚙️ Production notes

The current production-readiness pass makes the app easier to deploy and reason about:

- the FastAPI app is configured through environment variables
- the Docker image installs from the project metadata instead of a missing `requirements.txt`
- the DB path and asset directories are mounted and created predictably
- the app no longer relies on a permissive wildcard CORS origin in the default runtime shape

---

## 📋 Documentation map

- [docs/implementation.md](docs/implementation.md) — engineering walk-through and current architecture detail
- [docs/pipeline.md](docs/pipeline.md) — request/data processing flow and deployment model
- [docs/workdone.md](docs/workdone.md) — milestone log and progress notes

---

## 📄 License

MIT
