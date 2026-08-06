import io
import wave
import torch
import numpy as np
import typing
from unittest.mock import patch

# Monkey patch numpy for older libraries expecting broadcast_to in stride_tricks
if not hasattr(np.lib.stride_tricks, 'broadcast_to'):
    np.lib.stride_tricks.broadcast_to = np.broadcast_to

import os
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
        
        # Patch torch.load securely only during model load
        _original_torch_load = torch.load
        def _patched_torch_load(*args, **kwargs):
            kwargs.setdefault("weights_only", False)
            return _original_torch_load(*args, **kwargs)
            
        with patch("torch.load", _patched_torch_load):
            model.load_checkpoint(config, checkpoint_dir=str(model_path))
        
        import torch
        if torch.cuda.is_available():
            model.cuda()
            
        self._model = model
        self._config = config

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en", model_id: str = "", **kwargs: typing.Any) -> bytes:
        self._load_model()
        if not self._model.speaker_manager or not self._model.speaker_manager.speakers:
            raise RuntimeError("No speakers available in XTTS model.")
            
        speakers = list(self._model.speaker_manager.speakers.keys())
        speaker = "Claribel Dervla" if "Claribel Dervla" in speakers else speakers[0]
        
        if voice_id and voice_id != "auto" and voice_id in speakers:
            speaker = voice_id

        out = self._model.synthesize(
            text,
            config=self._config,
            speaker_wav=None,
            speaker_name=speaker,
            gpt_cond_len=3,
            language=language,
        )
        
        audio_array = out["wav"]
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

    def list_voices(self, model_id: str = "", **kwargs: typing.Any) -> list[dict]:
        self._load_model()
        if not self._model or not self._model.speaker_manager:
            return []
            
        voices = []
        for name in self._model.speaker_manager.speakers.keys():
            voices.append({"id": name, "name": name, "gender": "N", "language": "en"})
        return voices
