"""Shell tools with deny-by-default enforcement (not prompt-level).

Technical layer: a tool is only exposed if the current trust profile
allows it. Default profile = read-only commands only. This mirrors the
"permission rules are enforced by the runtime, not by the model" pattern
from Claude Code / Cline research (plan, Безопасность).

Profiles are intentionally simple for now; the full per-tool matrix with
wildcards/canonicalization lands with the GUI settings tab.
"""

from __future__ import annotations

import shlex
import subprocess

# Commands allowed with the default (read-only) profile.
_READONLY = {
    "ls", "cat", "head", "tail", "pwd", "echo", "date", "df", "du",
    "ps", "whoami", "uname", "git status", "git log", "git diff",
}

# Commands that are always blocked regardless of profile.
_ALWAYS_BLOCKED = {
    "rm", "mv", "dd", "mkfs", "shutdown", "reboot", "sudo",
    "powershell", "format", "del", "rd",
}


class ShellError(Exception):
    pass


def canonicalize(command: str) -> str:
    """Strip wrapping prefixes so matching sees the real command.

    `timeout 5 rm -rf /`, `nohup rm -rf /`, `env A=1 rm -rf /` all
    canonicalize to `rm -rf /` — otherwise deny lists are trivially
    bypassed with a prefix.
    """
    parts = command.strip().split()
    while parts:
        if parts[0] == "timeout":
            parts = parts[1:]
            while parts and (parts[0].startswith("-") or parts[0].isdigit()
                             or parts[0][:-1].isdigit() and parts[0][-1] in "smh"):
                parts = parts[1:]
            continue
        if parts[0] == "nohup":
            parts = parts[1:]
            continue
        if parts[0] == "env":
            parts = parts[1:]
            while parts and "=" in parts[0] and not parts[0].startswith("-"):
                parts = parts[1:]
            continue
        break
    return " ".join(parts)


class Shell:
    def __init__(self, profile: str = "readonly"):
        self.profile = profile

    def run(self, command: str, timeout: int = 30) -> str:
        cmd = canonicalize(command)
        if not cmd:
            raise ShellError("пустая команда")
        first = cmd.split(" ", 1)[0]
        if first in _ALWAYS_BLOCKED or cmd in _ALWAYS_BLOCKED:
            raise ShellError(f"команда запрещена: {first}")

        if self.profile == "readonly":
            if first not in _READONLY:
                raise ShellError(
                    f"профиль readonly запрещает: {first} "
                    "(разреши в настройках или смени профиль)"
                )
        # 'full' profile: everything except _ALWAYS_BLOCKED.

        try:
            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # Windows console output is cp1251/cp866, not utf-8
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ShellError(f"таймаут {timeout}s: {first}") from None

        out = (proc.stdout + proc.stderr).strip()
        return out or f"(exit {proc.returncode}, пусто)"

    def run_safe(self, command: str, timeout: int = 30) -> str:
        """Alias kept for CLI symmetry; same enforcement."""
        return self.run(command, timeout)


if __name__ == "__main__":  # pragma: no cover — runnable self-check
    assert canonicalize("timeout 5 rm -rf /tmp/x") == "rm -rf /tmp/x"
    assert canonicalize("nohup echo hi") == "echo hi"
    assert canonicalize("env A=1 ls -la") == "ls -la"
    sh = Shell("readonly")
    assert "test" in sh.run("echo test")
    for evil in ("rm -rf /tmp/x", "timeout 5 rm -rf /tmp/x", "nohup mv a b"):
        try:
            sh.run(evil)
            raise AssertionError(f"не заблокировано: {evil}")
        except ShellError:
            pass
    try:
        sh.run("curl http://x")
        raise AssertionError("curl не заблокирован в readonly")
    except ShellError:
        pass
    print("shell ok")
