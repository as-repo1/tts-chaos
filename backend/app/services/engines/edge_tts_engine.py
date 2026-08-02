from __future__ import annotations
import asyncio, io
from .base import TTSEngine

class EdgeTTSEngine(TTSEngine):
    name = "edge-tts"
    display_name = "Edge TTS (Cloud)"
    languages = ["en", "fr", "de", "es", "ja", "zh", "ar", "pt", "it", "ko"]
    quality_score = 70
    supports_styles = ["neutral", "cheerful", "sad", "angry", "fearful"]

    _VOICE_MAP = {
        "en": "en-US-JennyNeural",
        "fr": "fr-FR-DeniseNeural",
        "de": "de-DE-KatjaNeural",
        "es": "es-ES-ElviraNeural",
        "ja": "ja-JP-NanamiNeural",
        "zh": "zh-CN-XiaoxiaoNeural",
    }

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en") -> bytes:
        import edge_tts

        voice = voice_id if voice_id != "auto" else self._VOICE_MAP.get(language, "en-US-JennyNeural")
        rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"-{int((1.0 - speed) * 100)}%"
        pitch_str = f"+{int(pitch)}Hz" if pitch >= 0 else f"{int(pitch)}Hz"

        async def _run() -> bytes:
            buf = io.BytesIO()
            communicate = edge_tts.Communicate(text, voice, rate=rate_str, pitch=pitch_str)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()

        return asyncio.run(_run())

    def list_voices(self) -> list[dict]:
        return [
            {"id": "en-US-JennyNeural", "name": "Jenny (US)", "gender": "F", "language": "en"},
            {"id": "en-US-GuyNeural", "name": "Guy (US)", "gender": "M", "language": "en"},
            {"id": "en-GB-SoniaNeural", "name": "Sonia (GB)", "gender": "F", "language": "en"},
            {"id": "fr-FR-DeniseNeural", "name": "Denise (FR)", "gender": "F", "language": "fr"},
            {"id": "de-DE-KatjaNeural", "name": "Katja (DE)", "gender": "F", "language": "de"},
        ]
