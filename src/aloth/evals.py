"""Aloth evals: real tasks with checkable outcomes.

Each case is {prompt, check} where check(result: str) -> bool asserts the
outcome. Runs in a throwaway home so tests never touch real data.

Usage:
    ALOTH_HOME=$(mktemp -d) DEEPSEEK_API_KEY=... uv run python -m aloth.evals
Exit code: 0 = all pass, 1 = any fail.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from aloth.cli import _cmd_chat

# Cases are ordered: later cases may rely on facts saved by earlier ones.
CASES: list[dict] = [
    {
        "name": "time_tool",
        "prompt": "Который час по UTC? Используй тул current_time и назови год.",
        "check": lambda r: "20" in r and "26" in r,  # год 2026
    },
    {
        "name": "memory_save_and_see",
        "prompt": (
            "Сохрани в память факт: пользователь любит чай. "
            "Вызови тул memory_add. Потом скажи, что ты запомнил."
        ),
        "check": lambda r: "чай" in r.lower(),
    },
    {
        "name": "memory_persists_new_session",
        "prompt": "Что ты обо мне знаешь? Перечисли факты из памяти.",
        "check": lambda r: "чай" in r.lower(),
    },
    {
        "name": "file_write_read",
        "prompt": (
            "Запиши в файл data/test.txt строку 'eval-ok' через тул file_write, "
            "потом прочитай его тулом file_read и скажи, что внутри."
        ),
        "check": lambda r: "eval-ok" in r,
    },
    {
        "name": "web_search_returns_links",
        "prompt": (
            "Найди в интернете 'python asyncio' тулом search_web "
            "и скажи, сколько результатов вернулось."
        ),
        "check": lambda r: any(c.isdigit() for c in r) or "http" in r,
    },
]


def _fake_args(prompt: str) -> object:
    class A:
        message = prompt
        model = "deepseek:deepseek-chat"
        session = None  # fresh session per case
        history = 5

    return A()


def _run_cases() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []
    for case in CASES:
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            _cmd_chat(_fake_args(case["prompt"]))
        out = buf.getvalue()
        results.append((case["name"], case["check"](out), out[:200].replace("\n", " ")))
    return results


def main() -> int:
    results = _run_cases()
    failed = [r for r in results if not r[1]]
    for name, ok, snippet in results:
        print(f"{'PASS' if ok else 'FAIL'}  {name}  :: {snippet}")
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
