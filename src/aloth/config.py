"""Settings: ~/.aloth/config/settings.json (API-ключ, профиль доверия)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROFILES = ("readonly", "full")
SETTINGS_FILE = "settings.json"


@dataclass
class Settings:
    api_key: str = ""
    profile: str = "readonly"

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            raise ValueError(f"profile must be one of {PROFILES}, got {self.profile!r}")


def load(home: Path) -> Settings:
    path = home / "config" / SETTINGS_FILE
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Settings(api_key=data.get("api_key", ""),
                    profile=data.get("profile", "readonly"))


def save(home: Path, settings: Settings) -> None:
    (home / "config").mkdir(parents=True, exist_ok=True)
    path = home / "config" / SETTINGS_FILE
    path.write_text(
        json.dumps({"api_key": settings.api_key, "profile": settings.profile},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":  # pragma: no cover — self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        s = Settings(api_key="sk-test", profile="full")
        save(home, s)
        back = load(home)
        assert back == s, f"roundtrip failed: {back} != {s}"
        try:
            Settings(profile="admin")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid profile must raise ValueError")
    print("config ok")
