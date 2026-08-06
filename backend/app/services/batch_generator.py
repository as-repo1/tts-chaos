import asyncio
import os
import uuid
import tempfile
import logging
from typing import Dict, Any, List
import re
import shutil

from backend.app.services.generator import generate_audio_asset
from backend.app.db.store import voices_store, VoiceRecord

logger = logging.getLogger(__name__)

# In-memory job store for MVP
# TODO: In production, replace with SQLite or Redis for persistence across restarts
JOBS: Dict[str, Dict[str, Any]] = {}


def chunk_text(text: str, max_chars: int = 1500) -> List[str]:
    """
    Splits text into chunks <= max_chars, trying to break at sentence boundaries.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks: List[str] = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_chars:
            current_chunk += (" " + sentence if current_chunk else sentence)
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # If a single sentence exceeds max_chars, hard-split it
            if len(sentence) > max_chars:
                for i in range(0, len(sentence), max_chars):
                    chunks.append(sentence[i:i + max_chars])
                current_chunk = ""
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return [c for c in chunks if c.strip()]


async def _run_ffmpeg(*args: str) -> None:
    """Run an ffmpeg command asynchronously without blocking the event loop."""
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    retcode = await proc.wait()
    if retcode != 0:
        raise RuntimeError(f"ffmpeg exited with code {retcode}: ffmpeg {' '.join(args)}")


async def process_batch_job(job_id: str, text: str, voice_settings: dict, output_dir: str):
    """
    Background task that processes an entire document — splits, synthesizes, and merges.
    """
    job = JOBS[job_id]
    job["status"] = "running"

    strategy = voice_settings.get("chunking_strategy", "standard")
    if strategy == "semantic":
        from backend.app.services.semantic_analyzer import semantic_chunking
        chunks = semantic_chunking(text)
    else:
        chunks = chunk_text(text)
        
    total_chunks = len(chunks)
    job["total_chunks"] = total_chunks
    job["progress_percent"] = 0

    if total_chunks == 0:
        job["status"] = "completed"
        job["progress_percent"] = 100
        return

    work_dir = tempfile.mkdtemp(prefix=f"tts_batch_{job_id}_")

    # Create a 1-second silence WAV for natural paragraph pauses
    silence_path = os.path.join(work_dir, "silence.wav")
    try:
        await _run_ffmpeg(
            "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
            "-t", "1", silence_path
        )
    except Exception as e:
        logger.warning(f"Could not create silence.wav: {e}. Chunks will be concatenated without pauses.")
        silence_path = None

    chunk_files: List[str] = []
    chunk_idx = 0

    try:
        while chunk_idx < total_chunks:
            if job["status"] == "cancelled":
                return

            # Block here if the job is paused waiting for user action
            while job["status"] == "requires_action":
                await asyncio.sleep(1)

            if job["status"] == "cancelled":
                return

            chunk_text_str = chunks[chunk_idx]

            try:
                # generate_audio_asset is an async function now.
                model_id = voice_settings.get("model_id") or ""
                voice_name_chunk = f"{voice_settings.get('voice_name', 'chunk')}_{chunk_idx:04d}"

                asset = await generate_audio_asset(
                    text=chunk_text_str,
                    voice_name=voice_name_chunk,
                    language=voice_settings.get("language", "en"),
                    style=voice_settings.get("style", "neutral"),
                    model_id=model_id,
                    voice_id=voice_settings.get("voice_id", "default") or "default",
                    speed=voice_settings.get("speed", 1.0),
                    pitch=voice_settings.get("pitch", 0.0),
                    output_format="wav",  # Enforce WAV for clean concatenation
                )

                # Copy the generated file into our work dir for later merging
                chunk_file = os.path.join(work_dir, f"chunk_{chunk_idx:04d}.wav")
                shutil.copy2(asset["file_path"], chunk_file)
                chunk_files.append(chunk_file)

                job["chunks_completed"] = chunk_idx + 1
                job["progress_percent"] = int(((chunk_idx + 1) / total_chunks) * 90)
                chunk_idx += 1

            except Exception as e:
                logger.error(f"Chunk {chunk_idx} failed: {e}")
                job["status"] = "requires_action"
                job["error"] = str(e)
                job["failed_chunk_idx"] = chunk_idx

                # Wait for user action (retry / skip / cancel)
                while job["status"] == "requires_action":
                    await asyncio.sleep(1)

                if job["status"] == "skip_chunk":
                    job["status"] = "running"
                    chunk_idx += 1  # Skip this chunk
                elif job["status"] == "retry_chunk":
                    job["status"] = "running"
                    # chunk_idx stays the same → retry
                elif job["status"] == "cancelled":
                    return

        # ── Merge all chunks with ffmpeg ──────────────────────────────────────
        job["status"] = "merging"
        final_file = os.path.join(output_dir, f"{job_id}.wav")

        concat_txt_path = os.path.join(work_dir, "concat.txt")
        with open(concat_txt_path, "w") as f:
            for i, c_file in enumerate(chunk_files):
                f.write(f"file '{c_file}'\n")
                if silence_path and i < len(chunk_files) - 1:
                    f.write(f"file '{silence_path}'\n")

        await _run_ffmpeg(
            "-y", "-f", "concat", "-safe", "0",
            "-i", concat_txt_path, "-c", "copy", final_file
        )

        job["progress_percent"] = 100
        job["status"] = "completed"

        # Create a DB record for the merged audio
        file_size = os.path.getsize(final_file)
        record = VoiceRecord(
            id=job_id,
            voice_name=voice_settings.get("voice_name", "Document Audio"),
            language=voice_settings.get("language", "en"),
            style=voice_settings.get("style", "neutral"),
            text="[Document Batch Generation]",
            model_id=voice_settings.get("model_id") or "edge-tts",
            voice_id=voice_settings.get("voice_id"),
            speed=voice_settings.get("speed", 1.0),
            pitch=voice_settings.get("pitch", 0.0),
            file_path=final_file,
            file_size=file_size,
            duration_sec=None,
            output_format="wav",
        )
        await voices_store.save(record)
        job["voice_record"] = record.model_dump()

    except Exception as e:
        logger.error(f"Batch job {job_id} failed: {e}")
        job["status"] = "error"
        job["error"] = str(e)

    finally:
        # Always clean up the temp work directory
        try:
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass


def start_batch_job(text: str, voice_settings: dict, output_dir: str) -> str:
    """Create a new batch job and schedule it. Returns the job_id."""
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "progress_percent": 0,
        "total_chunks": 0,
        "chunks_completed": 0,
        "error": None,
    }

    # Schedule the async task on the running event loop
    loop = asyncio.get_running_loop()
    loop.create_task(process_batch_job(job_id, text, voice_settings, output_dir))
    return job_id


def get_job_status(job_id: str) -> Dict[str, Any]:
    return JOBS.get(job_id, {"status": "not_found"})


def submit_job_action(job_id: str, action: str):
    """Handle user action on a paused job: retry, skip, or cancel."""
    if job_id not in JOBS:
        return
    current_status = JOBS[job_id].get("status")
    if current_status == "requires_action":
        if action == "retry":
            JOBS[job_id]["status"] = "retry_chunk"
        elif action == "skip":
            JOBS[job_id]["status"] = "skip_chunk"
        elif action == "cancel":
            JOBS[job_id]["status"] = "cancelled"
    elif current_status in ("running", "queued"):
        # Allow cancel even when running
        if action == "cancel":
            JOBS[job_id]["status"] = "cancelled"
