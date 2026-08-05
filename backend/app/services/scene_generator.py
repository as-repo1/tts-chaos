from __future__ import annotations

import re
import os
import tempfile
import asyncio
import logging
from pathlib import Path

from backend.app.services.generator import generate_audio_asset, AUDIO_DIR
from backend.app.services.model_manager import model_manager

logger = logging.getLogger(__name__)

async def generate_scene(script: str, character_voices: dict, settings: dict) -> dict:
    """
    Parse a screenplay formatted script and generate audio for each dialog block.
    Concatenates the results using ffmpeg.
    
    [Alice] Hello there!
    [Bob] Hi!
    """
    lines = script.splitlines()
    blocks = []
    
    # Simple parsing: find [Name] and the text following it
    pattern = re.compile(r'^\s*\[([^\]]+)\]\s*(.*)$')
    
    current_char = None
    current_text = []
    
    for line in lines:
        match = pattern.match(line)
        if match:
            if current_char and current_text:
                blocks.append((current_char, " ".join(current_text)))
            current_char = match.group(1).strip()
            text_part = match.group(2).strip()
            current_text = [text_part] if text_part else []
        else:
            if current_char and line.strip():
                current_text.append(line.strip())
                
    if current_char and current_text:
        blocks.append((current_char, " ".join(current_text)))
        
    if not blocks:
        raise ValueError("No valid dialog blocks found in the script.")
        
    generated_files = []
    
    # Generate each block
    for char, text in blocks:
        char_config = character_voices.get(char)
        if not char_config:
            raise ValueError(f"No voice configuration found for character: {char}")
            
        model_id = char_config.get("model_id")
        if not model_id:
            # Need a model ID to proceed
            raise ValueError(f"No model_id specified for character: {char}")
            
        asset = generate_audio_asset(
            text=text,
            voice_name=char_config.get("voice_name", char),
            language=char_config.get("language", "en"),
            style=char_config.get("style", "neutral"),
            model_id=model_id,
            voice_id=char_config.get("voice_id", "default"),
            speed=char_config.get("speed", 1.0),
            pitch=char_config.get("pitch", 0.0),
            output_format="wav",
        )
        
        generated_files.append(asset["file_path"])
        
    # Concatenate using ffmpeg
    import datetime
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S%f")
    output_filename = f"scene_{timestamp}.wav"
    output_filepath = AUDIO_DIR / output_filename
    
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        for path in generated_files:
            f.write(f"file '{path}'\n")
        concat_list_path = f.name
        
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path, "-c", "copy", str(output_filepath)
    ]
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    
    # Clean up concat list
    try:
        os.remove(concat_list_path)
    except Exception:
        pass
        
    if proc.returncode != 0:
        err_msg = stderr.decode(errors="replace")[:500]
        logger.error("ffmpeg concat failed: %s", err_msg)
        raise RuntimeError(f"Scene concatenation failed: {err_msg}")
        
    return {
        "file_path": str(output_filepath),
        "file_name": output_filename,
        "blocks": len(blocks),
        "generated_parts": generated_files
    }
