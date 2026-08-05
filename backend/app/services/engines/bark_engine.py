from __future__ import annotations
import io
import logging
from .base import TTSEngine

logger = logging.getLogger(__name__)

class BarkEngine(TTSEngine):
    name = "bark"
    display_name = "Suno Bark"
    languages = ["en", "fr", "de", "es", "ja", "ko", "pt", "ru", "zh", "tr", "pl", "it"]
    quality_score = 90
    supports_styles = ["neutral", "expressive"]

    def __init__(self):
        super().__init__()
        self.processor = None
        self.model = None

    def is_available(self) -> bool:
        try:
            import transformers
            import scipy
            import torch
            return True
        except ImportError:
            return False

    def _load_model(self):
        if self.model is None or self.processor is None:
            import torch
            from transformers import AutoProcessor, BarkModel
            logger.info("Loading Bark model into memory...")
            model_id = "suno/bark-small" # Using small model for CPU/fast fallback
            self.processor = AutoProcessor.from_pretrained(model_id)
            
            # Use GPU if available, else CPU
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = BarkModel.from_pretrained(model_id).to(device)
            logger.info(f"Bark model loaded on {device}.")

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en", **kwargs) -> bytes:
        import scipy.io.wavfile
        import torch
        self._load_model()
        
        # If speed/pitch manipulation is required, Bark natively doesn't support it well,
        # but we can pass it off and let audio_processor handle it post-generation.
        
        # Bark supports voice presets. If "default" or "auto" is passed, use a default speaker
        preset = voice_id if voice_id not in ["auto", "default"] else "v2/en_speaker_6"
        
        inputs = self.processor(text, voice_preset=preset, return_tensors="pt")
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            audio_array = self.model.generate(**inputs, do_sample=True).cpu().numpy().squeeze()
            
        sample_rate = self.model.generation_config.sample_rate
        
        buf = io.BytesIO()
        scipy.io.wavfile.write(buf, rate=sample_rate, data=audio_array)
        buf.seek(0)
        return buf.read()
        
    def list_voices(self, **kwargs) -> list[dict]:
        # Bark has many presets, we'll expose a few notable ones for English
        return [
            {"id": "v2/en_speaker_6", "name": "English Male (Standard)", "gender": "M", "language": "en"},
            {"id": "v2/en_speaker_9", "name": "English Female (Standard)", "gender": "F", "language": "en"},
            {"id": "v2/en_speaker_1", "name": "English Male (Deep)", "gender": "M", "language": "en"},
            {"id": "v2/en_speaker_3", "name": "English Female (Energetic)", "gender": "F", "language": "en"},
            # A couple of other languages
            {"id": "v2/fr_speaker_1", "name": "French Female", "gender": "F", "language": "fr"},
            {"id": "v2/de_speaker_2", "name": "German Male", "gender": "M", "language": "de"},
        ]
