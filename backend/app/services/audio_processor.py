from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = {"wav", "mp3", "ogg", "flac"}


async def convert_audio(input_path: Path, output_format: str) -> Path:
    """
    Convert an audio file to the specified format using ffmpeg.
    Returns the path to the converted file.
    If the input is already in the target format, returns input_path unchanged.
    """
    if output_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {output_format}. Use one of: {SUPPORTED_FORMATS}")

    if input_path.suffix.lstrip(".") == output_format:
        return input_path

    output_path = input_path.with_suffix(f".{output_format}")

    codec_args = _get_codec_args(output_format)

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        *codec_args,
        str(output_path),
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        err_msg = stderr.decode(errors="replace")[:500]
        logger.error("ffmpeg conversion failed: %s", err_msg)
        raise RuntimeError(f"Audio conversion to {output_format} failed: {err_msg}")

    # Remove the original WAV if we successfully converted
    if output_path.exists() and input_path != output_path:
        input_path.unlink(missing_ok=True)

    logger.info("Converted %s → %s", input_path.name, output_path.name)
    return output_path


def convert_audio_sync(input_path: Path, output_format: str) -> Path:
    """Synchronous wrapper for convert_audio for use in non-async contexts."""
    import subprocess

    if output_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported format: {output_format}")

    if input_path.suffix.lstrip(".") == output_format:
        return input_path

    output_path = input_path.with_suffix(f".{output_format}")
    codec_args = _get_codec_args(output_format)

    cmd = ["ffmpeg", "-y", "-i", str(input_path), *codec_args, str(output_path)]

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=120,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Audio conversion failed: {result.stderr[:500]}")

    if output_path.exists() and input_path != output_path:
        input_path.unlink(missing_ok=True)

    return output_path


def _get_codec_args(fmt: str) -> list[str]:
    """Return ffmpeg codec arguments for the target format."""
    match fmt:
        case "mp3":
            return ["-codec:a", "libmp3lame", "-q:a", "2"]
        case "ogg":
            return ["-codec:a", "libvorbis", "-q:a", "6"]
        case "flac":
            return ["-codec:a", "flac", "-compression_level", "8"]
        case "wav":
            return ["-codec:a", "pcm_s16le"]
        case _:
            return []

async def apply_effects(input_path: Path, effects: dict) -> Path:
    """Apply audio effects to the given file using ffmpeg filters."""
    if not effects:
        return input_path
        
    filters = []
    if effects.get("reverb"):
        filters.append("aecho=0.8:0.9:1000:0.3")
    if effects.get("compressor"):
        filters.append("acompressor")
    if effects.get("eq"):
        filters.append("equalizer=f=1000:width_type=h:width=200:g=-3")
        
    if not filters:
        return input_path
        
    chain = ",".join(filters)
    output_path = input_path.with_name(f"{input_path.stem}_effects{input_path.suffix}")
    
    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-af", chain,
        str(output_path),
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    
    if proc.returncode != 0:
        err_msg = stderr.decode(errors="replace")[:500]
        logger.error("ffmpeg effects failed: %s", err_msg)
        raise RuntimeError(f"Audio effects application failed: {err_msg}")
        
    if output_path.exists():
        input_path.unlink(missing_ok=True)
        return output_path
    
    return input_path
