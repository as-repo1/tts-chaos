from __future__ import annotations

import aiosqlite
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from typing import Any

from pydantic import BaseModel, Field

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "voices.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CREATE_VOICES = """
CREATE TABLE IF NOT EXISTS voices (
    id              TEXT PRIMARY KEY,
    voice_name      TEXT NOT NULL,
    language        TEXT NOT NULL DEFAULT 'en',
    style           TEXT NOT NULL DEFAULT 'neutral',
    text            TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    voice_id        TEXT,
    speed           REAL NOT NULL DEFAULT 1.0,
    pitch           REAL NOT NULL DEFAULT 0.0,
    file_path       TEXT NOT NULL,
    file_size       INTEGER,
    duration_sec    REAL,
    output_format   TEXT NOT NULL DEFAULT 'wav',
    created_at      TEXT NOT NULL
);
"""


class VoiceRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    voice_name: str
    language: str = "en"
    style: str = "neutral"
    text: str
    model_id: str
    voice_id: str | None = None
    speed: float = 1.0
    pitch: float = 0.0
    file_path: str
    file_size: int | None = None
    duration_sec: float | None = None
    output_format: str = "wav"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class VoiceStore:
    async def save(self, record: VoiceRecord) -> dict[str, Any]:
        payload = record.model_dump()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO voices VALUES (:id,:voice_name,:language,:style,:text,:model_id,"
                ":voice_id,:speed,:pitch,:file_path,:file_size,:duration_sec,:output_format,:created_at)",
                payload,
            )
            await db.commit()
        return payload

    async def delete(self, voice_id: str) -> bool:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("DELETE FROM voices WHERE id=?", (voice_id,))
            await db.commit()
            return cur.rowcount > 0


voices_store = VoiceStore()


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_VOICES)
        await db.commit()


async def save_voice(**kwargs) -> dict[str, Any]:
    record = {
        "id": str(uuid4()),
        "created_at": datetime.now(timezone.utc).isoformat(),
        **kwargs,
    }
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO voices VALUES (:id,:voice_name,:language,:style,:text,:model_id,"
            ":voice_id,:speed,:pitch,:file_path,:file_size,:duration_sec,:output_format,:created_at)",
            record,
        )
        await db.commit()
    return record


async def list_voices(offset: int = 0, limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM voices ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def get_voice(voice_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM voices WHERE id=?", (voice_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def delete_voice(voice_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM voices WHERE id=?", (voice_id,))
        await db.commit()
        return cur.rowcount > 0


async def search_voices(
    query: str = "",
    model_id: str = "",
    language: str = "",
    offset: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Full-text search with optional model and language filters."""
    conditions = []
    params: list = []

    if query:
        conditions.append("(text LIKE ? OR voice_name LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if model_id:
        conditions.append("model_id = ?")
        params.append(model_id)
    if language:
        conditions.append("language = ?")
        params.append(language)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT * FROM voices {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def count_voices(query: str = "", model_id: str = "", language: str = "") -> int:
    conditions = []
    params: list = []
    if query:
        conditions.append("(text LIKE ? OR voice_name LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    if model_id:
        conditions.append("model_id = ?")
        params.append(model_id)
    if language:
        conditions.append("language = ?")
        params.append(language)

    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = f"SELECT COUNT(*) FROM voices {where}"

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(sql, params) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        # Total count
        async with db.execute("SELECT COUNT(*) FROM voices") as cur:
            row = await cur.fetchone()
            total = row[0] if row else 0

        # Total duration
        async with db.execute("SELECT COALESCE(SUM(duration_sec), 0) FROM voices") as cur:
            row = await cur.fetchone()
            total_duration = round(row[0], 1) if row else 0.0

        # Total file size
        async with db.execute("SELECT COALESCE(SUM(file_size), 0) FROM voices") as cur:
            row = await cur.fetchone()
            total_size = row[0] if row else 0

        # Models used breakdown
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT model_id, COUNT(*) as cnt FROM voices GROUP BY model_id ORDER BY cnt DESC"
        ) as cur:
            models_used = [dict(r) for r in await cur.fetchall()]

        # Languages breakdown
        async with db.execute(
            "SELECT language, COUNT(*) as cnt FROM voices GROUP BY language ORDER BY cnt DESC"
        ) as cur:
            languages_used = [dict(r) for r in await cur.fetchall()]

    return {
        "total_voices": total,
        "total_duration_sec": total_duration,
        "total_size_bytes": total_size,
        "total_size_mb": round(total_size / 1_048_576, 1) if total_size else 0,
        "models_used": models_used,
        "languages_used": languages_used,
    }
