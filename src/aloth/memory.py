"""Memory level 1: short facts about the user, always in context.

SQLite-backed list of durable facts. The agent reads them on every run
and can add/forget facts via tools. (Level 2 RAG comes later.)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


class MemoryStore:
    def __init__(self, db_path: Path):
        # Tools run in the event-loop thread; single-threaded sequential use.
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def add(self, fact: str) -> None:
        now = _now()
        self._conn.execute(
            "INSERT INTO facts (fact, created_at, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(fact) DO UPDATE SET updated_at = excluded.updated_at",
            (fact, now, now),
        )
        self._conn.commit()

    def forget(self, fact: str) -> bool:
        cur = self._conn.execute("DELETE FROM facts WHERE fact = ?", (fact,))
        self._conn.commit()
        return cur.rowcount > 0

    def all(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT fact FROM facts ORDER BY updated_at DESC"
        ).fetchall()
        return [r["fact"] for r in rows]

    def close(self) -> None:
        self._conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        mem = MemoryStore(Path(td) / "m.db")
        mem.add("Пользователь работает ночью")
        mem.add("Пользователь работает ночью")  # dedupe
        assert len(mem.all()) == 1
        assert mem.forget("Пользователь работает ночью")
        assert not mem.all()
        mem.close()
    print("memory ok")
