from __future__ import annotations
from pathlib import Path
from .base import TTSEngine

MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "kokoro"

class KokoroEngine(TTSEngine):
    name = "kokoro-82m"
    display_name = "Kokoro 82M"
    languages = ["en"]
    quality_score = 85
    supports_styles = ["neutral", "soft", "dramatic"]

    _VOICES = [
        {"id": "af_heart", "name": "Heart (F)", "gender": "F", "language": "en"},
        {"id": "af_sky",   "name": "Sky (F)",   "gender": "F", "language": "en"},
        {"id": "am_adam",  "name": "Adam (M)",  "gender": "M", "language": "en"},
        {"id": "am_michael","name":"Michael (M)","gender": "M", "language": "en"},
        {"id": "bf_emma",  "name": "Emma (GB-F)","gender":"F", "language": "en"},
        {"id": "bm_lewis", "name": "Lewis (GB-M)","gender":"M","language": "en"},
    ]

    def __init__(self):
        self._model = None

    def is_available(self) -> bool:
        try:
            import kokoro_onnx  # noqa: F401
            model_file = MODELS_DIR / "kokoro-v1.0.onnx"
            return model_file.exists()
        except ImportError:
            return False

    def _load(self):
        if self._model is None:
            import kokoro_onnx
            import soundfile as sf  # noqa: F401
            self._kokoro = kokoro_onnx
            self._model = kokoro_onnx.Kokoro(
                str(MODELS_DIR / "kokoro-v1.0.onnx"),
                str(MODELS_DIR / "voices.bin"),
            )

    def generate(self, text: str, voice_id: str = "af_heart", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en") -> bytes:
        import io, soundfile as sf
        self._load()
        samples, sample_rate = self._model.create(text, voice=voice_id, speed=speed, lang="en-us")
        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format="WAV", subtype="PCM_16")
        buf.seek(0)
        return buf.read()

    def list_voices(self) -> list[dict]:
        return self._VOICES
