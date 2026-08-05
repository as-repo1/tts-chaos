from __future__ import annotations
import asyncio
import io
import logging
import concurrent.futures
from .base import TTSEngine

logger = logging.getLogger(__name__)

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2)

_VOICE_CACHE: list[dict] | None = None
_VOICE_CACHE_LOCK = asyncio.Lock() if hasattr(asyncio, 'Lock') else None

async def _fetch_all_voices() -> list[dict]:
    """Fetch the full Edge TTS voice catalog (400+ voices)."""
    global _VOICE_CACHE
    if _VOICE_CACHE is not None:
        return _VOICE_CACHE
    try:
        import edge_tts
        raw_voices = await edge_tts.list_voices()
        voices = []
        for v in raw_voices:
            lang_code = v.get("Locale", "en-US").split("-")[0]
            voices.append({
                "id": v["ShortName"],
                "name": v.get("FriendlyName", v["ShortName"]),
                "gender": "F" if v.get("Gender") == "Female" else "M",
                "language": lang_code,
                "locale": v.get("Locale", ""),
                "styles": v.get("StyleList", []),
            })
        _VOICE_CACHE = voices
        return voices
    except Exception as e:
        logger.warning("Failed to fetch Edge TTS voices: %s", e)
        return []


class EdgeTTSEngine(TTSEngine):
    name = "edge-tts"
    display_name = "Edge TTS (Cloud)"
    languages = ["en", "fr", "de", "es", "ja", "zh", "ar", "pt", "it", "ko",
                 "nl", "pl", "ru", "sv", "tr", "hi", "vi", "th", "id", "cs"]
    quality_score = 70
    supports_styles = ["neutral", "cheerful", "sad", "angry", "fearful"]

    _FALLBACK_VOICES = [
        {"id": "en-US-JennyNeural",     "name": "Jenny (US Female)",      "gender": "F", "language": "en"},
        {"id": "en-US-GuyNeural",        "name": "Guy (US Male)",          "gender": "M", "language": "en"},
        {"id": "en-US-AriaNeural",       "name": "Aria (US Female)",       "gender": "F", "language": "en"},
        {"id": "en-US-DavisNeural",      "name": "Davis (US Male)",        "gender": "M", "language": "en"},
        {"id": "en-GB-SoniaNeural",      "name": "Sonia (GB Female)",      "gender": "F", "language": "en"},
        {"id": "en-GB-RyanNeural",       "name": "Ryan (GB Male)",         "gender": "M", "language": "en"},
        {"id": "en-AU-NatashaNeural",    "name": "Natasha (AU Female)",    "gender": "F", "language": "en"},
        {"id": "en-IN-NeerjaNeural",     "name": "Neerja (IN Female)",     "gender": "F", "language": "en"},
        {"id": "fr-FR-DeniseNeural",     "name": "Denise (FR Female)",     "gender": "F", "language": "fr"},
        {"id": "fr-FR-HenriNeural",      "name": "Henri (FR Male)",        "gender": "M", "language": "fr"},
        {"id": "de-DE-KatjaNeural",      "name": "Katja (DE Female)",      "gender": "F", "language": "de"},
        {"id": "de-DE-ConradNeural",     "name": "Conrad (DE Male)",       "gender": "M", "language": "de"},
        {"id": "es-ES-ElviraNeural",     "name": "Elvira (ES Female)",     "gender": "F", "language": "es"},
        {"id": "es-MX-DaliaNeural",      "name": "Dalia (MX Female)",      "gender": "F", "language": "es"},
        {"id": "ja-JP-NanamiNeural",     "name": "Nanami (JP Female)",     "gender": "F", "language": "ja"},
        {"id": "ja-JP-KeitaNeural",      "name": "Keita (JP Male)",        "gender": "M", "language": "ja"},
        {"id": "zh-CN-XiaoxiaoNeural",   "name": "Xiaoxiao (CN Female)",   "gender": "F", "language": "zh"},
        {"id": "zh-CN-YunxiNeural",      "name": "Yunxi (CN Male)",        "gender": "M", "language": "zh"},
        {"id": "ko-KR-SunHiNeural",      "name": "Sun-Hi (KR Female)",     "gender": "F", "language": "ko"},
        {"id": "pt-BR-FranciscaNeural",  "name": "Francisca (BR Female)",  "gender": "F", "language": "pt"},
        {"id": "it-IT-ElsaNeural",       "name": "Elsa (IT Female)",       "gender": "F", "language": "it"},
        {"id": "ru-RU-SvetlanaNeural",   "name": "Svetlana (RU Female)",   "gender": "F", "language": "ru"},
        {"id": "ar-SA-ZariyahNeural",    "name": "Zariyah (SA Female)",    "gender": "F", "language": "ar"},
        {"id": "hi-IN-SwaraNeural",      "name": "Swara (IN Female)",      "gender": "F", "language": "hi"},
        {"id": "tr-TR-EmelNeural",       "name": "Emel (TR Female)",       "gender": "F", "language": "tr"},
    ]

    _VOICE_MAP = {
        "en": "en-US-JennyNeural", "fr": "fr-FR-DeniseNeural", "de": "de-DE-KatjaNeural",
        "es": "es-ES-ElviraNeural", "ja": "ja-JP-NanamiNeural", "zh": "zh-CN-XiaoxiaoNeural",
        "ar": "ar-SA-ZariyahNeural", "pt": "pt-BR-FranciscaNeural", "it": "it-IT-ElsaNeural",
        "ko": "ko-KR-SunHiNeural", "nl": "nl-NL-ColetteNeural", "pl": "pl-PL-AgnieszkaNeural",
        "ru": "ru-RU-SvetlanaNeural", "sv": "sv-SE-SofieNeural", "tr": "tr-TR-EmelNeural",
        "hi": "hi-IN-SwaraNeural", "vi": "vi-VN-HoaiMyNeural", "th": "th-TH-PremwadeeNeural",
        "id": "id-ID-GadisNeural", "cs": "cs-CZ-VlastaNeural",
    }

    def is_available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def generate(self, text: str, voice_id: str = "auto", speed: float = 1.0,
                 pitch: float = 0.0, language: str = "en", model_id: str = "", style: str = "", **kwargs: typing.Any) -> bytes:
        """Generate audio using edge-tts. Runs the async code in a thread
        to avoid 'asyncio.run() inside running loop' crashes."""
        import edge_tts
        from backend.app.services.voice_styles import get_style_params

        voice = voice_id if voice_id not in ("auto", "default") else self._VOICE_MAP.get(language, "en-US-JennyNeural")
        
        style_params = get_style_params(style)
        edge_style = style_params.get("edge_style")
        
        # Check if the requested voice supports this style
        if edge_style:
            voice_info = next((v for v in self.list_voices() if v["id"] == voice), None)
            supported_styles = voice_info["styles"] if voice_info and "styles" in voice_info else []
            if edge_style in supported_styles:
                text = f'<mstts:express-as style="{edge_style}">{text}</mstts:express-as>'

        rate_str = f"+{int((speed - 1.0) * 100)}%" if speed >= 1.0 else f"-{int((1.0 - speed) * 100)}%"
        pitch_str = f"+{int(pitch)}Hz" if pitch >= 0 else f"{int(pitch)}Hz"

        def _sync_generate() -> bytes:
            """Run in a dedicated thread with its own event loop."""
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(_async_generate(edge_tts, text, voice, rate_str, pitch_str))
            finally:
                loop.close()

        future = _EXECUTOR.submit(_sync_generate)
        return future.result(timeout=120)

    def list_voices(self, model_id: str = "", **kwargs: typing.Any) -> list[dict]:
        try:
            loop = asyncio.new_event_loop()
            voices = loop.run_until_complete(_fetch_all_voices())
            loop.close()
            return voices if voices else self._FALLBACK_VOICES
        except Exception:
            return self._FALLBACK_VOICES


async def _async_generate(edge_tts, text: str, voice: str, rate: str, pitch: str) -> bytes:
    for attempt in range(3):
        try:
            buf = io.BytesIO()
            communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue()
        except Exception as e:
            if attempt == 2:
                raise
            logger.warning(f"Edge TTS generation failed (attempt {attempt+1}): {e}. Retrying...")
            await asyncio.sleep(1)
