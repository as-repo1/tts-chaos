import io
import os
import wave
from pathlib import Path
from .base import TTSEngine

MODELS_DIR = Path(__file__).resolve().parents[4] / "models" / "xtts"

class XttsEngine(TTSEngine):
    name = "xtts"
    display_name = "Coqui XTTS v2"
    languages = ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh", "hu", "ko", "ja"]
    quality_score = 95
    supports_styles = ["neutral"]

    def __init__(self):
        super().__init__()
        self._model = None
        self._config = None

    def is_available(self) -> bool:
        try:
            import TTS  # noqa: F401
            import torch  # noqa: F401
            return (MODELS_DIR / "xtts-v2" / "model.pth").exists()
        except ImportError:
            return False

    def _load_model(self):
        if self._model is not None:
            return
            
        from TTS.tts.configs.xtts_config import XttsConfig
        from TTS.tts.models.xtts import Xtts

        model_path = MODELS_DIR / "xtts-v2"
        config_path = model_path / "config.json"
        
        config = XttsConfig()
        config.load_json(str(config_path))
        
        model = Xtts.init_from_config(config)
        model.load_checkpoint(config, checkpoint_dir=str(model_path))
        
        import torch
        if torch.cuda.is_available():
            model.cuda()
            
        self._model = model
        self._config = config

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en") -> bytes:
        raise NotImplementedError("Use generate_cloned instead.")

    def generate_cloned(self, text: str, ref_audio_path: str, language: str = "en") -> bytes:
        self._load_model()
        
        # Compute speaker conditioning latency and generate audio
        out = self._model.synthesize(
            text,
            config=self._config,
            speaker_wav=ref_audio_path,
            gpt_cond_len=3,
            language=language,
        )
        
        audio_array = out["wav"]
        
        # Convert to 16-bit PCM bytes
        import numpy as np
        audio_int16 = (audio_array * 32767).astype(np.int16)
        
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(audio_int16.tobytes())
            
        buf.seek(0)
        return buf.read()

    def list_voices(self) -> list[dict]:
        return []
