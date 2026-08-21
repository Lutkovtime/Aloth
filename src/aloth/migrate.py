"""Migrate: бэкап дома + перенос plaintext api_key из settings.json в keyring.

Миграция 0.1.0 → v2:
1) безусловный снимок config/ и data/ в ~/.aloth/backups/<timestamp>;
2) api_key из settings.json → secrets (Credential Manager, fallback при его отсутствии);
3) версия схемы sessions.db (PRAGMA user_version=1).
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from aloth import config, secrets
from aloth.sessions import schema_version


def _backup(home: Path) -> Path:
    """Снимок config/ и data/ (кроме логов) в home/backups/<год-месяц-день-часы-минуты-секунды>."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = home / "backups" / ts
    for sub in ("config", "data"):
        src = home / sub
        if src.is_dir():
            shutil.copytree(src, dest / sub,
                            ignore=shutil.ignore_patterns("logs", "*.log"))
    return dest


def migrate(home: Path) -> dict:
    """One-shot 0.1.0 → v2. Idempotent: повторный запуск делает только бэкап."""
    home.mkdir(parents=True, exist_ok=True)
    backup = _backup(home)

    sfile = home / "config" / config.SETTINGS_FILE
    key_moved = False
    if sfile.exists():
        data = json.loads(sfile.read_text(encoding="utf-8"))
        legacy = data.pop("api_key", None) or None
        if legacy:
            secrets.set_api_key(home, legacy)
            if secrets.backend(home) == "fallback":
                # keyring недоступен: set_api_key вернул ключ в файл — не затираем.
                data["api_key"] = legacy
                data[secrets.FALLBACK_FLAG] = True
            else:
                key_moved = True
            print(f"API-ключ перенесён из settings.json → {secrets.backend(home)}")
        data["version"] = config.SCHEMA_VERSION
        sfile.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    db = home / "data" / "sessions.db"
    if db.exists():
        conn = sqlite3.connect(str(db))
        v = schema_version(conn)
        if v < 1:
            conn.execute("PRAGMA user_version = 1")
            conn.commit()
        conn.close()
        print(f"sessions.db: schema v{max(v, 1)}")

    print(f"бэкап: {backup}")
    return {"backup": str(backup), "key_moved": key_moved}


if __name__ == "__main__":  # pragma: no cover — self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        sfile = home / "config" / "settings.json"
        sfile.parent.mkdir(parents=True)
        sfile.write_text(json.dumps({"api_key": "sk-legacy-1", "profile": "full"}),
                         encoding="utf-8")
        (home / "data").mkdir(parents=True)
        db = home / "data" / "sessions.db"
        conn = sqlite3.connect(str(db))
        conn.execute("CREATE TABLE t (x)")  # legacy db без user_version
        conn.commit()
        conn.close()

        migrate(home)

        # бэкап создан и содержит config/
        backups = list((home / "backups").iterdir())
        assert backups and backups[0].is_dir(), "бэкап не создан"
        assert (backups[0] / "config" / "settings.json").exists(), "бэкап без config/"

        # версия записана
        data = json.loads(sfile.read_text(encoding="utf-8"))
        assert data.get("version") == config.SCHEMA_VERSION

        # ключ: в keyring, либо (keyring недоступен) в fallback-файле с флагом
        if secrets.backend(home) == "keyring":
            assert secrets.get_api_key(home) == "sk-legacy-1", "ключ не в keyring"
            assert "api_key" not in data, "секрет должен быть удалён из settings.json"
            print("keyring доступен — проверен основной путь")
        else:
            assert data.get("api_key") == "sk-legacy-1"
            assert data.get(secrets.FALLBACK_FLAG) is True
            print("keyring недоступен — проверен fallback-путь")

        # schema_version прогнан
        conn = sqlite3.connect(str(db))
        assert schema_version(conn) == 1, "sessions.db должен быть v1"
        conn.close()

        # чистка: тестовый ключ не остаётся в настоящем хранилище
        secrets.delete_api_key(home)
    print("migrate ok")
