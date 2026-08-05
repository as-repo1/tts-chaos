from __future__ import annotations
from abc import ABC, abstractmethod
from pathlib import Path

class TTSEngine(ABC):
    """Abstract contract every TTS engine must implement."""

    name: str           # machine identifier, e.g. "kokoro"
    display_name: str   # human label, e.g. "Kokoro 82M"
    languages: list[str]
    quality_score: int  # 0–100, used by auto-selector
    supports_styles: list[str]

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine can be used right now."""
        ...

    @abstractmethod
    def generate(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0,
        pitch: float = 0.0,
        language: str = "en",
        model_id: str = "",
    ) -> bytes:
        """Return raw WAV bytes (PCM 16-bit, mono or stereo)."""
        ...

    def list_voices(self, model_id: str = "") -> list[dict]:
        """Return list of {id, name, gender, language} dicts."""
        return []
