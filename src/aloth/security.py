"""Security policy: per-tool matrix {enabled, autoApprove}, deny-by-default, audit log.

Source of truth is ~/.aloth/config/security.json. A tool with no entry
is DISABLED (deny-by-default, fail-closed). Every tool call is written to
the audit log (~/.aloth/data/audit.db). Enforcement is in code — the model
never decides permissions, it just asks.

`autoApprove` is stored now and enforced when the GUI settings tab lands
(ask-before-action for autoApprove=false). Today every enabled tool is
callable; the matrix already gates which tools exist at all.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Tools known to the agent. Unknown names are disabled automatically.
KNOWN_TOOLS = (
    "current_time",
    "memory_add",
    "memory_forget",
    "file_read",
    "file_write",
    "search_web",
    "run_command",
)

# Defaults: reads are auto-approved, writes/commands ask (once GUI HITL exists).
_DEFAULTS = {
    "current_time": {"enabled": True, "autoApprove": True},
    "memory_add": {"enabled": True, "autoApprove": False},
    "memory_forget": {"enabled": True, "autoApprove": False},
    "file_read": {"enabled": True, "autoApprove": True},
    "file_write": {"enabled": True, "autoApprove": False},
    "search_web": {"enabled": True, "autoApprove": True},
    "run_command": {"enabled": True, "autoApprove": False},
}

_AUDIT_SCHEMA = """
CREATE TABLE IF NOT EXISTS actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    tool TEXT NOT NULL,
    args TEXT NOT NULL,
    allowed INTEGER NOT NULL,
    reason TEXT NOT NULL
);
"""


class SecurityPolicy:
    def __init__(self, config_path: Path, audit_path: Path):
        self.config_path = config_path
        self._tools = dict(_DEFAULTS)
        self._load()
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(audit_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_AUDIT_SCHEMA)
        self._conn.commit()

    @classmethod
    def load(cls, home: Path) -> SecurityPolicy:
        return cls(home / "config" / "security.json", home / "data" / "audit.db")

    def _load(self) -> None:
        if self.config_path.exists():
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
            self._tools = {**self._tools, **data}

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(self._tools, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def tool_enabled(self, name: str) -> bool:
        entry = self._tools.get(name)
        return bool(entry and entry.get("enabled"))

    def set_tool(self, name: str, enabled: bool, auto_approve: bool | None = None) -> None:
        entry = self._tools.setdefault(name, dict(_DEFAULTS.get(name, {"enabled": False, "autoApprove": False})))
        entry["enabled"] = enabled
        if auto_approve is not None:
            entry["autoApprove"] = auto_approve

    def matrix(self) -> dict:
        return {k: dict(v) for k, v in self._tools.items()}

    def log(self, tool: str, args: str, allowed: bool, reason: str) -> None:
        self._conn.execute(
            "INSERT INTO actions (ts, tool, args, allowed, reason) VALUES (?, ?, ?, ?, ?)",
            (_now(), tool, args[:500], int(allowed), reason),
        )
        self._conn.commit()

    def recent(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT ts, tool, args, allowed, reason FROM actions "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        self._conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        pol = SecurityPolicy.load(home)
        # deny-by-default: unknown tool is disabled
        assert not pol.tool_enabled("rm_rf")
        assert pol.tool_enabled("run_command")
        pol.log("run_command", "echo hi", True, "ok")
        pol.log("run_command", "rm -rf /", False, "запрещено")
        assert len(pol.recent()) == 2
        pol.set_tool("search_web", False)
        assert not pol.tool_enabled("search_web")
        pol.save()
        assert (home / "config" / "security.json").exists()
        pol.close()
    print("security ok")
