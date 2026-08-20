"""Agent core: PydanticAI loop with tools. Minimal by design.

One agent + tools + instructions — the simplest loop that works.
Model string 'deepseek:deepseek-chat' is resolved by PydanticAI 2.x
natively; API key comes from DEEPSEEK_API_KEY env var.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from pydantic_ai import Agent, RunContext

from aloth.memory import MemoryStore

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
) -> Agent:
    if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ALOTH_API_KEY")):
        raise ValueError("API key missing: set DEEPSEEK_API_KEY or ALOTH_API_KEY")

    facts = memory.all() if memory else []
    prompt = system_prompt
    if facts:
        prompt += "\n\nФакты о пользователе:\n- " + "\n- ".join(facts)

    agent = Agent(model, system_prompt=prompt)

    @agent.tool
    def current_time(ctx: RunContext[None]) -> str:
        """Current date and time (UTC)."""
        return datetime.now(timezone.utc).isoformat()

    if memory is not None:

        @agent.tool
        def memory_add(ctx: RunContext[None], fact: str) -> str:
            """Save a durable fact about the user (preferences, environment)."""
            memory.add(fact)
            return "запомнил"

        @agent.tool
        def memory_forget(ctx: RunContext[None], fact: str) -> str:
            """Remove a previously saved fact."""
            return "удалено" if memory.forget(fact) else "не найдено"

    return agent
