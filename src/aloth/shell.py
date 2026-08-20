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


class Shell:
    def __init__(self, profile: str = "readonly"):
        self.profile = profile

    def run(self, command: str, timeout: int = 30) -> str:
        cmd = command.strip()
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
    sh = Shell("readonly")
    assert "test" in sh.run("echo test")
    try:
        sh.run("rm -rf /tmp/x")
        raise AssertionError("rm не заблокирован")
    except ShellError:
        pass
    try:
        sh.run("curl http://x")
        raise AssertionError("curl не заблокирован в readonly")
    except ShellError:
        pass
    print("shell ok")
