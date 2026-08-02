from __future__ import annotations

import aiosqlite
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from typing import Any

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

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_VOICES)
        await db.commit()

async def save_voice(**kwargs) -> dict[str, Any]:
    record = {
        "id": str(uuid4()),
        "created_at": datetime.utcnow().isoformat(),
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
