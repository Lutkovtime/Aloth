"""Agent core: PydanticAI loop with tools. Minimal by design.

One agent + tools + instructions — the simplest loop that works.
Model string 'deepseek:deepseek-chat' is resolved by PydanticAI 2.x
natively; API key comes from DEEPSEEK_API_KEY env var.

Security: when a SecurityPolicy is passed, tools are exposed only if
enabled in the policy (deny-by-default), and every call is audited.
Enforcement is in code, never in the prompt.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from pydantic_ai import Agent, RunContext

from aloth.files import FileTools
from aloth.memory import MemoryStore
from aloth.security import SecurityPolicy
from aloth.shell import Shell, ShellError
from aloth.web import web_search

DEFAULT_MODEL = "deepseek:deepseek-chat"

SYSTEM_PROMPT = (
    "Ты — Aloth (Amazing Sloth), дружелюбный персональный ассистент. "
    "Отвечай коротко, по делу, на русском. Если не знаешь — так и скажи."
)


def build_agent(
    *,
    model: str = DEFAULT_MODEL,
    system_prompt: str = SYSTEM_PROMPT,
    memory: MemoryStore | None = None,
    files: FileTools | None = None,
    shell: Shell | None = None,
    security: SecurityPolicy | None = None,
) -> Agent:
    if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ALOTH_API_KEY")):
        raise ValueError("API key missing: set DEEPSEEK_API_KEY or ALOTH_API_KEY")

    facts = memory.all() if memory else []
    prompt = system_prompt
    if facts:
        prompt += "\n\nФакты о пользователе:\n- " + "\n- ".join(facts)

    agent = Agent(model, system_prompt=prompt)

    def _enabled(name: str) -> bool:
        return security is None or security.tool_enabled(name)

    def _audit(name: str, args: str, allowed: bool, reason: str = "ok") -> None:
        if security is not None:
            security.log(name, args, allowed, reason)

    if _enabled("current_time"):

        @agent.tool
        def current_time(ctx: RunContext[None]) -> str:
            """Current date and time (UTC)."""
            value = datetime.now(timezone.utc).isoformat()
            _audit("current_time", "", True)
            return value

    if memory is not None and _enabled("memory_add"):

        @agent.tool
        def memory_add(ctx: RunContext[None], fact: str) -> str:
            """Save a durable fact about the user (preferences, environment)."""
            memory.add(fact)
            _audit("memory_add", fact, True)
            return "запомнил"

    if memory is not None and _enabled("memory_forget"):

        @agent.tool
        def memory_forget(ctx: RunContext[None], fact: str) -> str:
            """Remove a previously saved fact."""
            removed = memory.forget(fact)
            _audit("memory_forget", fact, removed, "ok" if removed else "не найдено")
            return "удалено" if removed else "не найдено"

    if files is not None and _enabled("file_read"):

        @agent.tool
        def file_read(ctx: RunContext[None], path: str) -> str:
            """Read a file inside the agent home (~/.aloth). Path is home-relative."""
            try:
                value = files.read(path)
            except ValueError as e:
                _audit("file_read", path, False, str(e))
                raise
            _audit("file_read", path, True)
            return value

    if files is not None and _enabled("file_write"):

        @agent.tool
        def file_write(ctx: RunContext[None], path: str, content: str) -> str:
            """Write a file inside the agent home (~/.aloth). Path is home-relative."""
            try:
                value = files.write(path, content)
            except ValueError as e:
                _audit("file_write", path, False, str(e))
                raise
            _audit("file_write", f"{path}: {content[:100]}", True)
            return value

    if _enabled("search_web"):

        @agent.tool
        def search_web(ctx: RunContext[None], query: str) -> str:
            """Search the web (read-only). Returns titles and URLs."""
            value = web_search(query)
            _audit("search_web", query, True)
            return value

    if shell is not None and _enabled("run_command"):

        @agent.tool
        def run_command(ctx: RunContext[None], command: str) -> str:
            """Run a shell command (allowed by the current trust profile)."""
            try:
                value = shell.run(command)
            except ShellError as e:
                _audit("run_command", command, False, str(e))
                return f"запрещено: {e}"
            _audit("run_command", command, True)
            return value

    return agent
