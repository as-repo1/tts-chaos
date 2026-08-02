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
            for onnx in MODELS_DIR.glob("**/*.onnx"):
                if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                    return True
            return False
        except ImportError:
            return False

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en") -> bytes:
        from piper import PiperVoice
        model_path = self._find_model(language)
        if model_path is None:
            raise RuntimeError(f"No complete Piper model installed for language '{language}'")

        voice = PiperVoice.load(str(model_path))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            # Piper's native synthesize accepts wave file object
            try:
                voice.synthesize(text, wav, length_scale=1.0 / speed if speed > 0 else 1.0)
            except TypeError:
                # Fallback if length_scale is not supported in this version signature
                voice.synthesize(text, wav)

        buf.seek(0)
        return buf.read()

    def _find_model(self, language: str) -> Path | None:
        for onnx in MODELS_DIR.glob(f"{language}_*/*.onnx"):
            if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                return onnx
        for onnx in MODELS_DIR.glob("**/*.onnx"):
            if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                return onnx
        return None

    def list_voices(self) -> list[dict]:
        voices = []
        for onnx in MODELS_DIR.glob("**/*.onnx"):
            if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                lang = onnx.parent.name.split("_")[0]
                voices.append({"id": onnx.stem, "name": onnx.stem.replace("-", " ").title(),
                               "gender": "N", "language": lang})
        return voices
