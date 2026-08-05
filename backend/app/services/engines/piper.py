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
                 pitch: float = 0.0, language: str = "en", **kwargs) -> bytes:
        from piper import PiperVoice
        model_id = kwargs.get("model_id", "")
        model_path = self._find_model(language, model_id)
        if model_path is None:
            raise RuntimeError(f"No complete Piper model installed for language '{language}'")

        voice = PiperVoice.load(str(model_path))
        
        from piper import SynthesisConfig
        syn_config = SynthesisConfig(length_scale=1.0 / speed if speed > 0 else 1.0)
        
        audio_chunks = voice.synthesize(text, syn_config)
        import numpy as np
        
        audio_data = []
        for chunk in audio_chunks:
            audio_data.append(chunk.audio_float_array)
            
        if not audio_data:
            return b""
            
        audio_np = np.concatenate(audio_data)
        audio_int16 = (audio_np * 32767).astype(np.int16)
        
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(voice.config.sample_rate)
            wav.writeframes(audio_int16.tobytes())

        buf.seek(0)
        return buf.read()

    def _find_model(self, language: str, model_id: str = "") -> Path | None:
        if model_id:
            # e.g., piper-en-amy-medium -> en_US-amy-medium
            parts = model_id.split("-")
            if len(parts) >= 4:
                expected_stem = f"{parts[1]}_*-{'-'.join(parts[2:])}*"
                for onnx in MODELS_DIR.glob(f"**/{expected_stem}.onnx"):
                    if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                        return onnx

        # Fallback to language
        for onnx in MODELS_DIR.glob(f"{language}_*/*.onnx"):
            if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                return onnx
        for onnx in MODELS_DIR.glob("**/*.onnx"):
            if Path(f"{onnx}.json").exists() or onnx.with_suffix(".json").exists():
                return onnx
        return None

    def list_voices(self, **kwargs) -> list[dict]:
        # Piper models are self-contained voices, so return empty to use Default Persona
        return []
