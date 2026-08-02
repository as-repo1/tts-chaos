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
