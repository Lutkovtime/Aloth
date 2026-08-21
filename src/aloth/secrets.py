"""Secrets: API-ключ в Windows Credential Manager (keyring) с fallback на settings.json.

Keyring недоступен (CI, headless-сессия, сбой бэкенда) → plaintext-fallback
в settings.json с флагом api_key_plaintext_fallback=true и предупреждением.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    import keyring
except ImportError:  # pragma: no cover — зависимость гарантирована в pyproject
    keyring = None  # type: ignore[assignment]

SERVICE = "aloth"
FALLBACK_FLAG = "api_key_plaintext_fallback"


def _username(home: Path) -> str:
    """Per-home credential name: tempdir/self-check никогда не трогает настоящий ключ."""
    return str(home.resolve())


def _keyring_ok() -> bool:
    """True если keyring реально отвечает (не только импортируется)."""
    if keyring is None:
        return False
    try:
        keyring.get_password(SERVICE, "__aloth_probe__")
        return True
    except Exception:  # noqa: BLE001 — любой сбой бэкенда = fallback
        return False


def backend(home: Path) -> str:
    """Где сейчас хранится ключ: 'keyring' или 'fallback'."""
    return "keyring" if _keyring_ok() else "fallback"


def set_api_key(home: Path, key: str) -> None:
    """Store the API key; an empty string removes it."""
    if not key:
        delete_api_key(home)
        return
    if _keyring_ok():
        keyring.set_password(SERVICE, _username(home), key)
        _remove_fallback(home)
        return
    print("Предупреждение: keyring недоступен — ключ будет храниться в открытом виде "
          f"в settings.json ({FALLBACK_FLAG}=true).", file=sys.stderr)
    _write_fallback(home, key)


def get_api_key(home: Path) -> str:
    """Return the stored API key, or '' when none is set."""
    if _keyring_ok():
        key = keyring.get_password(SERVICE, _username(home))
        if key:
            return key
    return _fallback_key(home)


def delete_api_key(home: Path) -> None:
    """Remove the API key from keyring and from the fallback file."""
    if keyring is not None:
        try:
            keyring.delete_password(SERVICE, _username(home))
        except Exception:  # noqa: BLE001 — нет такого пароля или бэкенд упал
            pass
    _remove_fallback(home)


def _settings_path(home: Path) -> Path:
    return home / "config" / "settings.json"


def _read_settings(home: Path) -> dict:
    p = _settings_path(home)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_settings(home: Path, data: dict) -> None:
    p = _settings_path(home)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _fallback_key(home: Path) -> str:
    return str(_read_settings(home).get("api_key", ""))


def _write_fallback(home: Path, key: str) -> None:
    data = _read_settings(home)
    data["api_key"] = key
    data[FALLBACK_FLAG] = True
    _write_settings(home, data)


def _remove_fallback(home: Path) -> None:
    p = _settings_path(home)
    if not p.exists():
        return
    data = _read_settings(home)
    if "api_key" not in data and FALLBACK_FLAG not in data:
        return
    data.pop("api_key", None)
    data.pop(FALLBACK_FLAG, None)
    _write_settings(home, data)


if __name__ == "__main__":  # pragma: no cover — self-check
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        set_api_key(home, "sk-test-123")
        assert get_api_key(home) == "sk-test-123", "set/get round-trip failed"
        assert backend(home) in ("keyring", "fallback")
        if backend(home) == "fallback":
            assert _read_settings(home).get(FALLBACK_FLAG) is True
        delete_api_key(home)
        assert get_api_key(home) == "", "delete failed"
        print(f"secrets ok (backend={backend(home)})")
