from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).resolve().parents[3] / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_DIR = Path(__file__).resolve().parents[3] / "generated_audio"


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
    use_cases: list[str] = field(default_factory=list) # e.g. "audiobook", "podcast", "narrator", "poet", "persona", "cloning"
    hf_repo: str | None = None
    hf_filename: str | None = None
    download_url: str | None = None
    is_cloud: bool = False
    extra_files: list[tuple[str, str]] = field(default_factory=list)
    rename_map: dict[str, str] = field(default_factory=dict)
    pip_packages: list[str] = field(default_factory=list)


# ── Catalog ──────────────────────────────────────────────────────────────────

MODEL_CATALOG: list[ModelInfo] = [
    # --- Edge TTS ---
    ModelInfo(
        model_id="edge-tts",
        display_name="Edge TTS (Cloud)",
        engine="edge-tts",
        description="Microsoft Azure Neural TTS — 400+ voices, 60+ languages. Zero download, always available.",
        size_mb=0,
        languages=["en","fr","de","es","ja","zh","ar","pt","it","ko","nl","pl","ru","sv","tr","hi","bn","vi","th","id","cs"],
        supported_styles=["neutral","cheerful","sad","angry"],
        quality_score=70,
        use_cases=["narrator", "podcast", "audiobook"],
        is_cloud=True,
    ),
    
    # --- XTTS v2 ---
    ModelInfo(
        model_id="xtts-v2",
        display_name="Coqui XTTS v2 (Voice Cloning)",
        engine="xtts",
        description="Zero-shot voice cloning. Mimic any voice using just a 3-second audio sample.",
        size_mb=2100,
        languages=["en","es","fr","de","it","pt","pl","tr","ru","nl","cs","ar","zh","hu","ko","ja","hi","bn"],
        supported_styles=["neutral"],
        quality_score=95,
        use_cases=["cloning", "podcast", "persona"],
        hf_repo="coqui/XTTS-v2",
        hf_filename="model.pth",
        extra_files=[
            ("https://huggingface.co/coqui/XTTS-v2/resolve/main/config.json", "config.json"),
            ("https://huggingface.co/coqui/XTTS-v2/resolve/main/vocab.json", "vocab.json"),
        ],
        pip_packages=["TTS"],
    ),
    
    # --- Kokoro ---
    ModelInfo(
        model_id="kokoro-82m",
        display_name="Kokoro 82M",
        engine="kokoro",
        description="State-of-the-art English TTS at only 82M parameters. ONNX inference.",
        size_mb=350,
        languages=["en"],
        supported_styles=["neutral","soft","dramatic"],
        quality_score=88,
        use_cases=["narrator", "podcast", "audiobook"],
        hf_repo="onnx-community/Kokoro-82M-v1.0-ONNX",
        hf_filename="model.onnx",
        extra_files=[
            ("https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin", "voices-v1.0.bin"),
        ],
        rename_map={"model.onnx": "kokoro-v1.0.onnx", "voices-v1.0.bin": "voices.bin"},
    ),
    
    # --- Suno Bark ---
    ModelInfo(
        model_id="bark-small",
        display_name="Suno Bark (Small)",
        engine="bark",
        description="Transformer-based text-to-audio model capable of highly expressive speech and non-speech sounds like [laughs] and [sighs].",
        size_mb=1200,
        languages=["en", "fr", "de", "es", "ja", "ko", "pt", "ru", "zh", "tr", "pl", "it"],
        supported_styles=["neutral", "expressive"],
        quality_score=90,
        use_cases=["persona", "cloning", "expressive"],
        is_cloud=False,
        pip_packages=["transformers", "scipy", "torch"],
    ),
    
    # --- Piper Models (High Quality) ---
    ModelInfo(
        model_id="piper-en-libritts-high",
        display_name="Libritts (Multi-Speaker)",
        engine="piper",
        description="High quality American English. Over 900 distinct speakers. Great for varied character roles.",
        size_mb=122,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=85,
        use_cases=["audiobook", "persona"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts/high/en_US-libritts-high.onnx",
        hf_filename="en_US-libritts-high.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts/high/en_US-libritts-high.onnx.json", "en_US-libritts-high.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-en-ryan-high",
        display_name="Ryan (Male Narrator)",
        engine="piper",
        description="Deep, clear male voice. Perfect for professional narrations and audiobooks.",
        size_mb=98,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=85,
        use_cases=["narrator", "audiobook", "podcast"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx",
        hf_filename="en_US-ryan-high.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json", "en_US-ryan-high.onnx.json"),
        ],
    ),
    
    # --- Piper Models (Medium Quality Personas) ---
    ModelInfo(
        model_id="piper-en-amy-medium",
        display_name="Amy (Female Podcast)",
        engine="piper",
        description="Warm, engaging female voice. Excellent for podcasts and conversational reading.",
        size_mb=61,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=78,
        use_cases=["podcast", "narrator"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx",
        hf_filename="en_US-amy-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium/en_US-amy-medium.onnx.json", "en_US-amy-medium.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-en-arctic-medium",
        display_name="Arctic (Expressive Poet)",
        engine="piper",
        description="Expressive, slightly dramatic reading style. Great for poetry and emotional texts.",
        size_mb=62,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=77,
        use_cases=["poet", "persona"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/arctic/medium/en_US-arctic-medium.onnx",
        hf_filename="en_US-arctic-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/arctic/medium/en_US-arctic-medium.onnx.json", "en_US-arctic-medium.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-en-alan-medium",
        display_name="Alan (British Male)",
        engine="piper",
        description="Clear British (UK) male voice.",
        size_mb=60,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=75,
        use_cases=["persona", "narrator"],
        pip_packages=["piper-tts"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        hf_filename="en_GB-alan-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json", "en_GB-alan-medium.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-en-alba-medium",
        display_name="Alba (British Female)",
        engine="piper",
        description="Clear British (UK) female voice.",
        size_mb=63,
        languages=["en"],
        supported_styles=["neutral"],
        quality_score=76,
        use_cases=["persona", "podcast"],
        pip_packages=["piper-tts"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alba/medium/en_GB-alba-medium.onnx",
        hf_filename="en_GB-alba-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_GB/alba/medium/en_GB-alba-medium.onnx.json", "en_GB-alba-medium.onnx.json"),
        ],
    ),
    
    # --- Non-English ---
    ModelInfo(
        model_id="piper-fr-siwis-medium",
        display_name="Siwis (French)",
        engine="piper",
        description="Standard French female narrator.",
        size_mb=62,
        languages=["fr"],
        supported_styles=["neutral"],
        quality_score=75,
        use_cases=["narrator", "audiobook"],
        pip_packages=["piper-tts"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx",
        hf_filename="fr_FR-siwis-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json", "fr_FR-siwis-medium.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-de-thorsten-high",
        display_name="Thorsten (German)",
        engine="piper",
        description="High quality German male voice.",
        size_mb=100,
        languages=["de"],
        supported_styles=["neutral"],
        quality_score=85,
        use_cases=["narrator", "podcast"],
        pip_packages=["piper-tts"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx",
        hf_filename="de_DE-thorsten-high.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/de/de_DE/thorsten/high/de_DE-thorsten-high.onnx.json", "de_DE-thorsten-high.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-hi-pratham-medium",
        display_name="Pratham (Hindi)",
        engine="piper",
        description="Clear Hindi male voice.",
        size_mb=68,
        languages=["hi"],
        supported_styles=["neutral"],
        quality_score=75,
        use_cases=["narrator", "podcast"],
        pip_packages=["piper-tts"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
        hf_filename="hi_IN-pratham-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json", "hi_IN-pratham-medium.onnx.json"),
        ],
    ),
    ModelInfo(
        model_id="piper-bn-multi-medium",
        display_name="Multi-Speaker (Bengali)",
        engine="piper",
        description="Medium quality Bengali voice with multiple speakers.",
        size_mb=65,
        languages=["bn"],
        supported_styles=["neutral"],
        quality_score=72,
        use_cases=["narrator", "podcast"],
        pip_packages=["piper-tts"],
        download_url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/bn/bn_BD/multi/medium/bn_BD-multi-medium.onnx",
        hf_filename="bn_BD-multi-medium.onnx",
        extra_files=[
            ("https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/bn/bn_BD/multi/medium/bn_BD-multi-medium.onnx.json", "bn_BD-multi-medium.onnx.json"),
        ],
    ),
]


def _dir_size_mb(path: Path) -> float:
    """Get total size of a directory in MB."""
    if not path.exists():
        return 0.0
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / 1_048_576, 1)


class ModelManager:
    def __init__(self):
        self._engines: dict[str, object] = {}
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

    # ── System Info ───────────────────────────────────────────────────────────

    def get_disk_usage(self) -> dict:
        return {
            "models_mb": _dir_size_mb(MODELS_DIR),
            "audio_mb": _dir_size_mb(AUDIO_DIR),
            "models_dir": str(MODELS_DIR),
            "audio_dir": str(AUDIO_DIR),
        }

    # ── Download ──────────────────────────────────────────────────────────────

    async def download(self, model_id: str) -> asyncio.Queue:
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
                    dest_name = info.hf_filename or info.download_url.split("/")[-1]
                    files_to_download.append((info.download_url, dest_name))
                elif info.hf_repo and info.hf_filename:
                    url = f"https://huggingface.co/{info.hf_repo}/resolve/main/{info.hf_filename}"
                    files_to_download.append((url, info.hf_filename))
                for url, name in (info.extra_files or []):
                    files_to_download.append((url, name))

                for url, dest_name in files_to_download:
                    await queue.put({"event": "download_started", "file": dest_name})
                    await _stream_file(url, dest_dir / dest_name, queue, model_id)
                    
                    if dest_name in info.rename_map:
                        rename_to = info.rename_map[dest_name]
                        (dest_dir / dest_name).rename(dest_dir / rename_to)

                if info.pip_packages:
                    import subprocess
                    import sys
                    await queue.put({"event": "download_started", "file": f"Installing packages: {', '.join(info.pip_packages)}"})
                    try:
                        subprocess.run(
                            [sys.executable, "-m", "pip", "install", *info.pip_packages],
                            check=True,
                            capture_output=True
                        )
                    except subprocess.CalledProcessError as e:
                        logger.error(f"Failed to install pip packages: {e.stderr.decode()}")
                        raise RuntimeError(f"Failed to install Python dependencies for {model_id}")

                await queue.put({"event": "download_complete", "model_id": model_id})
                self._scan_installed()
            except Exception as exc:
                logger.exception("Download failed for %s", model_id)
                if 'dest_dir' in locals() and dest_dir.exists():
                    for f in dest_dir.iterdir():
                        if f.is_file():
                            f.unlink()
                await queue.put({"event": "download_error", "error": str(exc)})
            finally:
                self._progress.pop(model_id, None)

        asyncio.create_task(_download_task())
        return queue

    # ── Engine access ─────────────────────────────────────────────────────────

    def get_engine(self, model_id: str):
        if model_id not in self._engines:
            self._load_engine(model_id)
        engine = self._engines.get(model_id)
        if engine is None:
            raise RuntimeError(f"Engine for '{model_id}' could not be loaded")
        return engine

    # ── Private ───────────────────────────────────────────────────────────────

    def _scan_installed(self):
        from .engines.edge_tts_engine import EdgeTTSEngine
        from .engines.kokoro import KokoroEngine
        from .engines.piper import PiperEngine

        engine_map = {
            "edge-tts": EdgeTTSEngine,
            "kokoro-82m": KokoroEngine,
        }

        # Add all piper and bark models from catalog
        for m in MODEL_CATALOG:
            if m.model_id.startswith("piper-"):
                engine_map[m.model_id] = PiperEngine
            elif m.model_id == "bark-small":
                try:
                    from .engines.bark_engine import BarkEngine
                    engine_map["bark-small"] = BarkEngine
                except ImportError:
                    pass
            elif m.model_id == "xtts-v2":
                try:
                    from .engines.xtts_engine import XttsEngine
                    engine_map["xtts-v2"] = XttsEngine
                except ImportError:
                    pass

        for model_id, cls in engine_map.items():
            try:
                inst = cls()
                if inst.is_available():
                    self._engines[model_id] = inst
            except Exception:
                logger.debug("Engine %s not available", model_id, exc_info=True)
                
        logger.info("Scanning engines: found %s", list(self._engines.keys()))

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
