"""Sessions: SQLite + FTS5, one table for messages, full-text search.

Keeps the full conversation history on disk so any session can be
reopened and searched — the same shape Hermes uses.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'Новая сессия',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content, content='messages', content_rowid='id'
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
"""

SCHEMA_VERSION = 1


def schema_version(conn: sqlite3.Connection) -> int:
    """Current schema version stored in PRAGMA user_version."""
    return int(conn.execute("PRAGMA user_version").fetchone()[0])


class SessionStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def create_session(self, title: str = "Новая сессия") -> str:
        sid = uuid.uuid4().hex[:12]
        self._conn.execute(
            "INSERT INTO sessions (id, title, created_at) VALUES (?, ?, ?)",
            (sid, title, _now()),
        )
        self._conn.commit()
        return sid

    def add_message(self, session_id: str, role: str, content: str) -> None:
        self._conn.execute(
            "INSERT INTO messages (session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (session_id, role, content, _now()),
        )
        self._conn.commit()

    def list_sessions(self, limit: int = 100) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, title, created_at FROM sessions "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def history(self, session_id: str, limit: int = 50) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE session_id = ? "
            "ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        rows = self._conn.execute(
            "SELECT m.session_id, m.role, m.content, m.created_at "
            "FROM messages_fts f JOIN messages m ON m.id = f.rowid "
            "WHERE messages_fts MATCH ? ORDER BY m.id DESC LIMIT ?",
            (query, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        store = SessionStore(Path(td) / "s.db")
        conn = sqlite3.connect(str(Path(td) / "s.db"))
        assert schema_version(conn) == SCHEMA_VERSION
        conn.close()
        sid = store.create_session("тест")
        store.add_message(sid, "user", "привет мир")
        store.add_message(sid, "assistant", "и тебе привет")
        assert store.history(sid) and store.search("привет")
        store.close()
    print("sessions ok")
