"""SQLite database connection management."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

_SCHEMA_PATH = Path(__file__).parent / "schemas.sql"


async def get_connection(db_path: str = "llmfuzz.db") -> aiosqlite.Connection:
    """Open a connection and ensure the schema exists."""
    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.executescript(_SCHEMA_PATH.read_text())
    await conn.commit()
    return conn
