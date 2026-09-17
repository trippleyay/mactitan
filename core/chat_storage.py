"""
Persistent per-chat conversation history, backed by a local SQLite file.
Survives restarts/redeploys — the in-memory dict this replaces did not.

SQLite is a single file on disk, no separate database service to run or
pay for — appropriate for a single-instance deployment. If this ever needs
to run across multiple backend instances, this would need to move to a
shared store (e.g. Redis or a hosted Postgres) — noted here explicitly
rather than silently assumed to be fine.
"""

import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "chat_history.db"


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            chat_id INTEGER PRIMARY KEY,
            history_json TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


def get_history(chat_id: int) -> list[dict] | None:
    """Return the stored conversation history for a chat_id, or None if none exists yet."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT history_json FROM chat_history WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def save_history(chat_id: int, history: list[dict]) -> None:
    """Persist the conversation history for a chat_id, overwriting any previous state."""
    conn = _get_connection()
    try:
        conn.execute(
            """
            INSERT INTO chat_history (chat_id, history_json, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                history_json = excluded.history_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (chat_id, json.dumps(history)),
        )
        conn.commit()
    finally:
        conn.close()
