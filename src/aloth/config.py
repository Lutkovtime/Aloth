"""Settings: ~/.aloth/config/settings.json (профиль доверия, уровень UI).

API-ключ сюда НЕ пишется: он живёт в Windows Credential Manager
(см. aloth.secrets). settings.json хранит только не-секретные настройки.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PROFILES = ("readonly", "full")
UI_LEVELS = ("simple", "advanced")
SETTINGS_FILE = "settings.json"
# Версия схемы settings.json; legacy-файлы 0.1.0 без поля version считаются "1".
SCHEMA_VERSION = "2"


@dataclass
class Settings:
    profile: str = "readonly"
    ui_level: str = "simple"
    version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.profile not in PROFILES:
            raise ValueError(f"profile must be one of {PROFILES}, got {self.profile!r}")
        if self.ui_level not in UI_LEVELS:
            raise ValueError(f"ui_level must be one of {UI_LEVELS}, got {self.ui_level!r}")

    def is_advanced(self) -> bool:
        """True если включён продвинутый уровень UI (единственный источник правды)."""
        return self.ui_level == "advanced"


def load(home: Path) -> Settings:
    path = home / "config" / SETTINGS_FILE
    if not path.exists():
        return Settings()
    data = json.loads(path.read_text(encoding="utf-8"))
    return Settings(profile=data.get("profile", "readonly"),
                    ui_level=data.get("ui_level", "simple"),
                    version=data.get("version", "1"))


def save(home: Path, settings: Settings) -> None:
    (home / "config").mkdir(parents=True, exist_ok=True)
    path = home / "config" / SETTINGS_FILE
    # Неизвестные поля сохраняем как есть (напр. plaintext-fallback ключ при
    # недоступном keyring), но сами никогда не пишем секрет.
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    data.update({"profile": settings.profile,
                 "ui_level": settings.ui_level,
                 "version": settings.version})
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover — self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        s = Settings(profile="full", ui_level="advanced")
        save(home, s)
        back = load(home)
        assert back == s, f"roundtrip failed: {back} != {s}"
        raw = (home / "config" / SETTINGS_FILE).read_text(encoding="utf-8")
        assert "api_key" not in raw, "секрет не должен попадать в settings.json"
        assert back.is_advanced() and not Settings().is_advanced()
        try:
            Settings(ui_level="pro")
        except ValueError:
            pass
        else:
            raise AssertionError("invalid ui_level must raise ValueError")
    print("config ok")
