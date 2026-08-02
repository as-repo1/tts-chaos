# 🎙️ TTS Chaos — AI Voice Studio

A full-stack, self-hosted Text-to-Speech studio built with **FastAPI** (backend) and **vanilla HTML/CSS/JS** (frontend). Browse, download, and manage TTS models directly from the UI, then synthesize voices from text with a single click.

---

## ✨ Features

| Feature | Description |
|---|---|
| **Real TTS Engines** | Kokoro-82M · Piper TTS · Coqui XTTS-v2 · Edge-TTS (cloud fallback) |
| **Auto Model Selector** | Picks the best installed model per language, style, and quality |
| **In-App Downloads** | Browse the model catalog and download models with real-time progress |
| **Voice Library** | All generated voices saved, playable inline, and downloadable |
| **Premium UI** | Glassmorphism dark-mode SPA with animated waveform visualizer |
| **REST API** | Full JSON API — every feature is accessible programmatically |

---

## 🗂️ Project Structure

```
tts-chaos/
├── README.md                   ← you are here
├── pipeline.md                 ← CI/CD and data flow pipeline
├── implementation.md           ← step-by-step development guide
├── pyproject.toml              ← Python project config + dependencies
│
├── backend/
│   ├── __init__.py
│   └── app/
│       ├── main.py             ← FastAPI app entrypoint + lifespan
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py       ← Voice CRUD endpoints
│       │   ├── models_router.py← Model catalog + download endpoints
│       │   └── events.py       ← SSE (Server-Sent Events) streams
│       ├── services/
│       │   ├── __init__.py
│       │   ├── generator.py    ← TTS dispatch + WAV writer
│       │   ├── model_selector.py← Smart auto-selection logic
│       │   ├── model_manager.py ← Download / install / delete
│       │   └── engines/
│       │       ├── base.py     ← Abstract TTSEngine interface
│       │       ├── kokoro.py   ← Kokoro-82M (ONNX)
│       │       ├── piper.py    ← Piper TTS
│       │       ├── xtts.py     ← Coqui XTTS-v2
│       │       └── edge_tts_engine.py ← Edge-TTS (cloud)
│       └── db/
│           ├── __init__.py
│           └── store.py        ← SQLite via aiosqlite
│
├── frontend/
│   ├── index.html              ← SPA shell (3 tabs)
│   └── static/
│       ├── app.css             ← Glassmorphism design system
│       └── app.js              ← Modular vanilla JS
│
├── models/                     ← Downloaded model files (auto-created)
│   ├── kokoro/
│   ├── piper/
│   └── xtts/
│
└── generated_audio/            ← Synthesized WAV/MP3 files (auto-created)
```

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- `uv` package manager (recommended) or `pip`
- Optional: NVIDIA GPU + CUDA for XTTS acceleration
- Optional: `ffmpeg` for MP3 export

### 2. Install

```bash
git clone https://github.com/yourusername/tts-chaos.git
cd tts-chaos

# Using Docker (Recommended)
docker-compose up -d

# OR Manual Setup
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
```

### 3. Run

```bash
source .venv/bin/activate
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 2002
```

2. Open `http://localhost:2002` in your browser.

### 4. First Steps

1. Click the **Models** tab
2. Find **Edge-TTS** (no download — cloud) and click **Activate**
3. Switch to the **Studio** tab
4. Type your text and click **Create Voice**
5. Check the **Library** tab to play and download your voice

---

## 🔌 API Reference

Base URL: `http://localhost:8000`

### Voice Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/voice` | Create a new voice |
| `GET` | `/api/voices` | List all voices (pagination supported) |
| `GET` | `/api/voices/{id}/audio` | Stream audio (supports Range requests) |
| `DELETE` | `/api/voices/{id}` | Delete voice + audio file |

**POST /api/voice — Request Body**
```json
{
  "text": "Hello from TTS Chaos",
  "voice_name": "my-voice",
  "language": "en",
  "style": "neutral",
  "model_id": null,
  "voice_id": "af_heart",
  "speed": 1.0,
  "pitch": 0.0,
  "output_format": "wav"
}
```

### Model Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/models/catalog` | All known models with install status |
| `GET` | `/api/models/installed` | Installed models only |
| `POST` | `/api/models/download/{model_id}` | Start background download |
| `GET` | `/api/models/download/{model_id}/progress` | SSE download progress stream |
| `DELETE` | `/api/models/{model_id}` | Remove installed model |
| `GET` | `/api/models/{model_id}/voices` | List available voices for model |
| `GET` | `/api/models/recommend` | Auto-selector recommendation |

---

## 🤖 Supported TTS Models

| Model | Engine | Size | Languages | GPU |
|---|---|---|---|---|
| **Kokoro-82M** | kokoro-onnx | ~350 MB | English | Optional |
| **Piper (en_US-lessac)** | piper-tts | ~63 MB | 30+ langs | CPU only |
| **Coqui XTTS-v2** | TTS library | ~1.8 GB | 17 langs | Recommended |
| **Edge-TTS** | edge-tts | 0 MB | 60+ langs | None (cloud) |

---

## ⚙️ Configuration

All configuration is via environment variables (or `.env` file):

```env
HOST=0.0.0.0
PORT=8000
MODELS_DIR=./models
AUDIO_DIR=./generated_audio
DB_PATH=./backend/app/data/voices.db
DEFAULT_MODEL=auto
DEFAULT_LANGUAGE=en
DEFAULT_FORMAT=wav
MAX_CONCURRENT_GENERATIONS=4
```

---

## 📋 Roadmap

- [x] Phase 1: Real engine layer (Edge-TTS, Kokoro, Piper, XTTS)
- [x] Phase 2: Model management API + SSE progress
- [x] Phase 3: Premium frontend (glassmorphism SPA)
- [ ] Phase 4: Batch generation + voice cloning
- [ ] Phase 5: Docker packaging

---

## 📄 License

MIT
