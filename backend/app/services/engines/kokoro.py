from __future__ import annotations
import typing
from pathlib import Path
from .base import TTSEngine

MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "kokoro" / "kokoro-82m"

class KokoroEngine(TTSEngine):
    name = "kokoro-82m"
    display_name = "Kokoro 82M"
    languages = ["en"]
    quality_score = 85
    supports_styles = ["neutral", "soft", "dramatic"]

    _VOICES = [
        {"id": "af_heart", "name": "Heart (US Female)", "gender": "F", "language": "en"},
        {"id": "af_sky", "name": "Sky (US Female)", "gender": "F", "language": "en"},
        {"id": "af_bella", "name": "Bella (US Female)", "gender": "F", "language": "en"},
        {"id": "af_sarah", "name": "Sarah (US Female)", "gender": "F", "language": "en"},
        {"id": "af_nicole", "name": "Nicole (US Female)", "gender": "F", "language": "en"},
        {"id": "am_adam", "name": "Adam (US Male)", "gender": "M", "language": "en"},
        {"id": "am_michael", "name": "Michael (US Male)", "gender": "M", "language": "en"},
        {"id": "bf_emma", "name": "Emma (GB Female)", "gender": "F", "language": "en"},
        {"id": "bf_isabella", "name": "Isabella (GB Female)", "gender": "F", "language": "en"},
        {"id": "bm_george", "name": "George (GB Male)", "gender": "M", "language": "en"},
        {"id": "bm_lewis", "name": "Lewis (GB Male)", "gender": "M", "language": "en"},
        {"id": "bm_daniel", "name": "Daniel (GB Male)", "gender": "M", "language": "en"},
    ]

    def __init__(self):
        self._model = None

    def is_available(self) -> bool:
        try:
            import kokoro_onnx  # noqa: F401
            model_file = MODELS_DIR / "kokoro-v1.0.onnx"
            model_file_alt = MODELS_DIR / "model.onnx"
            return model_file.exists() or model_file_alt.exists()
        except ImportError:
            return False

    def _load(self):
        if self._model is None:
            import kokoro_onnx
            import soundfile as sf  # noqa: F401
            self._kokoro = kokoro_onnx
            
            model_path = MODELS_DIR / "kokoro-v1.0.onnx"
            if not model_path.exists():
                model_path = MODELS_DIR / "model.onnx"
                
            voices_path = MODELS_DIR / "voices.bin"
            if not voices_path.exists():
                voices_path = MODELS_DIR / "voices-v1.0.bin"
                
            self._model = kokoro_onnx.Kokoro(
                str(model_path),
                str(voices_path),
            )

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en", model_id: str = "", **kwargs: typing.Any) -> bytes:
        import io, soundfile as sf
        self._load()
        samples, sample_rate = self._model.create(text, voice=voice_id, speed=speed, lang="en-us")
        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read()

    def list_voices(self, model_id: str = "", **kwargs: typing.Any) -> list[dict]:
        return self._VOICES
