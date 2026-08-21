"""Health check: config, API key, network, disk, RAM, logs — ✓/✗ with actions.

run_health(home, ui_level) returns a ready-to-print text block. Two levels:
'simple' — what is wrong and what to do; 'advanced' — paths, codes, sizes.
Registration in the CLI is done by the lead (aloth health).
"""

from __future__ import annotations

import ctypes
import json
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path

import httpx
import keyring

from aloth import config
from aloth.logging import LOG_FILE, setup_logging

_DISK_MIN_MB = 500
_RAM_MIN_MB = 1024
_NET_TIMEOUT = 5.0
_NET_URL = "https://api.deepseek.com"


def _api_key(home: Path) -> str:
    """API key via aloth.secrets (keyring → settings.json fallback).

    Defensive: if secrets.py is absent/broken (lead's refactor in flight),
    fall back to direct keyring lookup, then the legacy plaintext api_key.
    """
    try:
        from aloth import secrets  # type: ignore[import-not-found]

        get = getattr(secrets, "get_api_key", None)
        if get:
            return get(home)
    except Exception:  # noqa: BLE001 — module absent or broken, fall through
        pass
    try:
        stored = keyring.get_password("aloth", "api_key") or ""
    except Exception:  # noqa: BLE001 — no keyring backend
        stored = ""
    if stored:
        return stored
    try:  # legacy fallback: plaintext api_key in settings.json (schema v1)
        p = home / "config" / config.SETTINGS_FILE
        if p.exists():
            return str(json.loads(p.read_text(encoding="utf-8")).get("api_key", ""))
    except Exception:  # noqa: BLE001 — broken json etc.
        pass
    return ""


def _free_ram_mb() -> int | None:
    """Free RAM in MB via GlobalMemoryStatusEx (Windows); None on other OSes."""
    if sys.platform != "win32":
        return None

    class _MS(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    st = _MS()
    st.dwLength = ctypes.sizeof(st)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
        return None
    return int(st.ullAvailPhys // (1024 * 1024))


def run_health(home: Path, ui_level: str = "simple") -> str:
    """Run all checks; return a ready-to-print ✓/✗ report (str)."""
    logger = setup_logging(home)
    rows: list[tuple[bool, str, str]] = []

    def add(ok: bool, simple: str, advanced: str = "") -> None:
        rows.append((ok, simple, advanced))
        if not ok:
            logger.warning("health: %s", advanced or simple)

    # 1. Config file present and readable.
    cfg_path = home / "config" / config.SETTINGS_FILE
    try:
        config.load(home)
        cfg_ok, cfg_err = cfg_path.exists(), ""
    except Exception as e:  # noqa: BLE001 — broken JSON etc.
        cfg_ok, cfg_err = False, str(e)
    add(cfg_ok,
        "Конфиг читается." if cfg_ok else "Конфиг не найден. Запусти aloth setup.",
        f"config: {cfg_path}" + (f" — {cfg_err}" if cfg_err else ""))

    # 2. API key present.
    key = _api_key(home)
    add(bool(key),
        "API-ключ есть." if key else "Нет API-ключа. Запусти aloth setup и введи ключ.",
        f"key: найден ({key[:6]}…)" if key
        else "key: не найден (keyring aloth/api_key, settings.json)")

    # 3. Network reachability.
    try:
        resp = httpx.get(_NET_URL, timeout=_NET_TIMEOUT)
        net_ok, net_d = True, f"HTTP {resp.status_code}, {resp.elapsed.total_seconds():.2f}s"
    except Exception as e:  # noqa: BLE001 — DNS/TLS/timeout
        net_ok, net_d = False, str(e)
    add(net_ok,
        "Интернет доступен." if net_ok else "Нет сети. Проверь подключение и повтори.",
        f"net: GET {_NET_URL} — {net_d}")

    # 4. Free disk space on the home drive.
    free_mb = shutil.disk_usage(home).free // (1024 * 1024)
    add(free_mb >= _DISK_MIN_MB,
        f"На диске {free_mb} МБ свободно." if free_mb >= _DISK_MIN_MB
        else f"Мало места: {free_mb} МБ. Освободи диск (нужно ≥ {_DISK_MIN_MB} МБ).",
        f"disk: {free_mb} МБ свободно на {home.drive or home.anchor}, порог {_DISK_MIN_MB} МБ")

    # 5. Free RAM.
    ram_mb = _free_ram_mb()
    if ram_mb is None:
        add(True, "Память: не проверяется на этой ОС.",
            "ram: GlobalMemoryStatusEx доступен только на Windows")
    else:
        add(ram_mb >= _RAM_MIN_MB,
            f"Свободно {ram_mb} МБ ОЗУ." if ram_mb >= _RAM_MIN_MB
            else f"Мало памяти: {ram_mb} МБ. Закрой тяжёлые программы.",
            f"ram: {ram_mb} МБ свободно, порог {_RAM_MIN_MB} МБ")

    # 6. Log file exists and was written recently.
    log_file = home / "logs" / LOG_FILE
    if log_file.exists():
        age_h = (time.time() - log_file.stat().st_mtime) / 3600
        log_ok = age_h < 24
        add(log_ok,
            "Лог пишется." if log_ok else "Лог давно не обновлялся. Запусти приложение.",
            f"log: {log_file}, запись {age_h:.1f} ч назад, {log_file.stat().st_size} байт")
    else:
        add(False, "Лог не найден. Запусти приложение хотя бы раз.",
            f"log: {log_file} отсутствует")

    head = "Проверка здоровья Aloth"
    lines = [head, "-" * len(head)]
    for ok, simple, advanced in rows:
        lines.append(f"{'✓' if ok else '✗'} {simple}")
        if ui_level == "advanced" and advanced:
            lines.append(f"    {advanced}")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    with tempfile.TemporaryDirectory() as td:
        home = Path(td)
        from aloth import secrets

        secrets.set_api_key(home, "sk-test")  # real key path, per-home credential
        try:
            simple = run_health(home, "simple")
            advanced = run_health(home, "advanced")
            assert isinstance(simple, str) and simple.strip(), "empty simple report"
            assert "✓" in simple and "✗" in simple, "both marks expected on fake home"
            assert len(advanced) > len(simple), "advanced must add detail lines"
            assert "log:" in advanced or "config:" in advanced
        finally:
            secrets.delete_api_key(home)
        logging.shutdown()  # close the handler so Windows can delete the tempdir
    print("health ok")
