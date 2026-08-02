from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .model_manager import ModelManager


def auto_select_model(
    text: str,
    language: str,
    style: str,
    model_manager: "ModelManager",
) -> str:
    """Score installed models and return the best model_id."""
    candidates = model_manager.list_installed()

    if not candidates:
        # Edge-TTS is always available as cloud fallback
        return "edge-tts"

    scores: list[tuple[int, str]] = []
    for m in candidates:
        score = 0
        # Language match
        if language in m.languages or language.split("-")[0] in m.languages:
            score += 50
        # Style support
        if style in m.supported_styles:
            score += 20
        # Intrinsic quality
        score += m.quality_score
        scores.append((score, m.model_id))

    scores.sort(key=lambda t: t[0], reverse=True)
    return scores[0][1]
