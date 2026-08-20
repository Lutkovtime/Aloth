"""The Aloth home directory: one place for everything the agent produces.

~/.aloth (Windows: %USERPROFILE%\.aloth)
  config/   settings, profiles
  data/     memory, databases, state
  skills/   user skills/plugins
  backups/  home snapshots
  logs/     rotated logs
  runtime/  pid, locks, cache
"""

from __future__ import annotations

import os
from pathlib import Path

HOME_ENV = "ALOTH_HOME"
DEFAULT_HOME = Path.home() / ".aloth"

SUBDIRS = ("config", "data", "skills", "backups", "logs", "runtime")


def home_dir() -> Path:
    """Resolve the Aloth home directory (env override, else ~/.aloth)."""
    override = os.environ.get(HOME_ENV)
    return Path(override).expanduser() if override else DEFAULT_HOME


def ensure_home() -> Path:
    """Create the home skeleton if missing; return the home path."""
    home = home_dir()
    for sub in SUBDIRS:
        (home / sub).mkdir(parents=True, exist_ok=True)
    return home


if __name__ == "__main__":  # pragma: no cover — trivial self-check
    h = ensure_home()
    assert h.exists() and all((h / s).is_dir() for s in SUBDIRS)
    print(f"home ok: {h}")
