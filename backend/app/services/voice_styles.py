from __future__ import annotations

"""
Voice style presets — maps abstract style names to engine-specific parameters.
Used by the Studio frontend to apply style modifications to TTS generation.
"""

STYLE_PRESETS: dict[str, dict] = {
    # ── Emotional Styles (primarily Edge TTS via SSML) ────────
    "neutral": {"speed": 1.0, "pitch": 0, "edge_style": None},
    "cheerful": {"speed": 1.05, "pitch": 2, "edge_style": "cheerful"},
    "sad": {"speed": 0.9, "pitch": -3, "edge_style": "sad"},
    "angry": {"speed": 1.1, "pitch": 3, "edge_style": "angry"},
    "fearful": {"speed": 1.05, "pitch": 1, "edge_style": "fearful"},
    "excited": {"speed": 1.15, "pitch": 4, "edge_style": "excited"},
    "friendly": {"speed": 1.0, "pitch": 1, "edge_style": "friendly"},
    "hopeful": {"speed": 0.95, "pitch": 1, "edge_style": "hopeful"},
    "whispering": {"speed": 0.8, "pitch": -2, "edge_style": "whispering"},
    "shouting": {"speed": 1.1, "pitch": 5, "edge_style": "shouting"},
    "terrified": {"speed": 1.2, "pitch": 2, "edge_style": "terrified"},
    "unfriendly": {"speed": 0.95, "pitch": -1, "edge_style": "unfriendly"},

    # ── Reading/Purpose Styles ────────────────────────────────
    "audiobook": {"speed": 0.85, "pitch": -2, "pause_scale": 1.5},
    "podcast": {"speed": 1.0, "pitch": 0, "pause_scale": 1.0},
    "newscast": {"speed": 0.95, "pitch": -1, "pause_scale": 0.8},
    "poetry": {"speed": 0.75, "pitch": 0, "pause_scale": 2.0},
    "narration": {"speed": 0.9, "pitch": -1, "pause_scale": 1.2},
    "documentary": {"speed": 0.88, "pitch": -2, "pause_scale": 1.3},
    "meditation": {"speed": 0.7, "pitch": -4, "pause_scale": 2.5},
    "storytelling": {"speed": 0.92, "pitch": 0, "pause_scale": 1.4},
}

# Styles that Edge TTS supports natively via SSML <mstts:express-as>
EDGE_NATIVE_STYLES = {
    "cheerful", "sad", "angry", "fearful", "excited", "friendly",
    "hopeful", "whispering", "shouting", "terrified", "unfriendly",
}


def get_style_params(style: str) -> dict:
    """Get the parameter overrides for a given style name."""
    return STYLE_PRESETS.get(style, STYLE_PRESETS["neutral"]).copy()


def list_styles() -> list[dict]:
    """Return all available styles with metadata for the frontend."""
    result = []
    for name, params in STYLE_PRESETS.items():
        category = "emotional" if params.get("edge_style") else "reading"
        result.append({
            "id": name,
            "name": name.replace("_", " ").title(),
            "category": category,
            "edge_native": name in EDGE_NATIVE_STYLES,
        })
    return result
