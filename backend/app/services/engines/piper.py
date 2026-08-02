from __future__ import annotations
import io, wave
from pathlib import Path
from .base import TTSEngine

MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "piper"

class PiperEngine(TTSEngine):
    name = "piper"
    display_name = "Piper TTS"
    languages = ["en", "de", "fr", "es", "nl", "it", "pt", "pl", "ru", "zh"]
    quality_score = 78
    supports_styles = ["neutral"]

    def is_available(self) -> bool:
        try:
            import piper  # noqa: F401
            return any(MODELS_DIR.glob("**/*.onnx"))
        except ImportError:
            return False

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en") -> bytes:
        from piper import PiperVoice
        # Find matching model for language
        model_path = self._find_model(language)
        if model_path is None:
            raise RuntimeError(f"No Piper model installed for language '{language}'")

        voice = PiperVoice.load(str(model_path))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(voice.config.sample_rate)
            for audio_bytes in voice.synthesize_stream_raw(text, length_scale=1.0/speed):
                wav.writeframes(audio_bytes)
        buf.seek(0)
        return buf.read()

    def _find_model(self, language: str) -> Path | None:
        # Prefer language-specific model, fall back to any installed
        for onnx in MODELS_DIR.glob(f"{language}_*/*.onnx"):
            return onnx
        for onnx in MODELS_DIR.glob("**/*.onnx"):
            return onnx
        return None

    def list_voices(self) -> list[dict]:
        voices = []
        for onnx in MODELS_DIR.glob("**/*.onnx"):
            lang = onnx.parent.name.split("_")[0]
            voices.append({"id": onnx.stem, "name": onnx.stem.replace("-", " ").title(),
                           "gender": "N", "language": lang})
        return voices
