"""Context compaction for long dialogs (PydanticAI).

Task 1.1 of the Aloth v2 roadmap. Compresses ``message_history`` between
``agent.iter()`` runs: once the history exceeds a threshold (~50% of the
comfortable window), old messages are collapsed into a "CONTEXT CHECKPOINT"
SystemPromptPart while the last N messages stay intact. Mechanics verified in
``spike/compaction_poc.py`` (summary as SystemPromptPart + ``protect_last_n``
works, summary survives into the final history).

Design notes:

- Pure stdlib + pydantic_ai. No LLM calls happen in this module: fact
  extraction and summarization are pluggable callables with deterministic
  heuristics as defaults. The lead can wire real agent turns into the
  ``extractor``/``summarizer`` hooks at integration time.
- The flush step (save important facts from the middle of the dialogue to
  files under the home dir) runs *before* the checkpoint is built, so facts
  survive even if the conversation is never continued.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    SystemPromptPart,
    UserPromptPart,
)

#: Compaction triggers. History is compacted when it exceeds EITHER bound —
#: both sit at ~50% of a comfortable window so we never run near the edge.
DEFAULT_MAX_MESSAGES = 12  # ~6 user turns
DEFAULT_MAX_CHARS = 24_000  # ~6k tokens of raw text
DEFAULT_PROTECT_LAST_N = 4  # last 2 full turns stay untouched

#: Marker every checkpoint carries; used by the PoC and by tests to detect
#: that a compaction happened.
_CHECKPOINT_MARKER = "CONTEXT CHECKPOINT"

#: Middle messages -> important facts (list of strings).
FactExtractor = Callable[[Sequence[ModelMessage]], list[str]]
#: (dropped messages, facts) -> checkpoint text.
Summarizer = Callable[[Sequence[ModelMessage], list[str]], str]


@dataclass
class CompactionResult:
    """Outcome of :func:`compact_history`.

    ``history`` is always a valid ``message_history`` for the next
    ``agent.iter()`` run; when nothing was compacted it is the input list
    unchanged and ``compacted`` is False.
    """

    history: list[ModelMessage]
    summary: str = ""
    facts: list[str] = field(default_factory=list)
    facts_file: Path | None = None
    compacted: bool = False


def _item_text(item: object) -> str:
    """Text of one UserContent item (str or dict with a 'content' key)."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("content", ""))
    return str(item)


def _part_text(part: object) -> str:
    """Plain text of a message part, whatever its content shape."""
    content = getattr(part, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, Sequence):
        return "\n".join(_item_text(item) for item in content)
    return ""


def estimate_size(messages: Sequence[ModelMessage]) -> int:
    """Total character length of all text parts in the history."""
    total = 0
    for message in messages:
        for part in getattr(message, "parts", ()):
            total += len(_part_text(part))
    return total


def extract_user_facts(messages: Sequence[ModelMessage]) -> list[str]:
    """Default extractor: user statements, deduplicated, order preserved.

    Good enough as a fallback — real extraction should be an LLM turn passed
    via ``extractor=``.
    """
    facts: list[str] = []
    seen: set[str] = set()
    for message in messages:
        for part in getattr(message, "parts", ()):
            if isinstance(part, UserPromptPart):
                text = _part_text(part).strip()
                if text and text not in seen:
                    seen.add(text)
                    facts.append(text)
    return facts


def default_summarizer(messages: Sequence[ModelMessage], facts: list[str]) -> str:
    """Default checkpoint text: the flushed facts, nothing else.

    The facts already carry what mattered (by default they are the user
    statements of the dropped region), so the checkpoint is just their
    enumeration — small, deterministic, no duplication.
    """
    if not facts:
        return f"{_CHECKPOINT_MARKER} (compacted history)\nNo key facts were preserved."
    lines = [f"{_CHECKPOINT_MARKER} (compacted history)", "Key facts preserved from the earlier dialogue:"]
    lines.extend(f"- {fact}" for fact in facts)
    return "\n".join(lines)


def flush_facts(
    messages: Sequence[ModelMessage],
    home_dir: Path | None = None,
    extractor: FactExtractor | None = None,
) -> tuple[list[str], Path | None]:
    """Extract important facts from the dialogue and persist them.

    The flush runs before compaction so facts from the middle of the dialog
    survive on disk even if the session is never continued. Facts are written
    to ``<home_dir>/context/checkpoint-<timestamp>.md`` when ``home_dir`` is
    given (``home_dir`` is the Aloth home itself, as returned by
    ``aloth.home.home_dir()``); the file is created only if there is at least
    one fact. Returns ``(facts, facts_file_or_None)``.
    """
    extract = extractor or extract_user_facts
    facts = extract(messages)
    if not facts or home_dir is None:
        return facts, None
    out_dir = Path(home_dir) / "context"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"checkpoint-{stamp}.md"
    path.write_text(
        "# Aloth context checkpoint\n\n"
        + "\n".join(f"- {fact}" for fact in facts)
        + "\n",
        encoding="utf-8",
    )
    return facts, path


def compact_history(
    messages: Sequence[ModelMessage],
    *,
    protect_last_n: int = DEFAULT_PROTECT_LAST_N,
    max_messages: int = DEFAULT_MAX_MESSAGES,
    max_chars: int = DEFAULT_MAX_CHARS,
    home_dir: Path | None = None,
    extractor: FactExtractor | None = None,
    summarizer: Summarizer | None = None,
) -> CompactionResult:
    """Compress an over-threshold history into a CONTEXT CHECKPOINT.

    Args:
        messages: Full ``message_history`` from ``agent.iter()``.
        protect_last_n: How many newest messages stay intact (default 4 =
            the last two full turns).
        max_messages: Compact when the history has more messages than this.
        max_chars: Compact when ``estimate_size`` exceeds this.
        home_dir: If set, facts from the dropped region are flushed to files
            under ``<home_dir>/context/`` before compression.
        extractor: Replaces the default fact extractor (e.g. an LLM turn).
        summarizer: Replaces the default checkpoint-text builder.

    Returns:
        :class:`CompactionResult`. ``history`` is ``[checkpoint, *tail]`` on
        compaction (exactly the shape validated in spike/compaction_poc.py),
        or the input unchanged when the thresholds are not exceeded.
    """
    hist = list(messages)
    if len(hist) <= max_messages and estimate_size(hist) <= max_chars:
        return CompactionResult(hist)

    drop_n = len(hist) - protect_last_n
    if drop_n <= 0:
        # Nothing left to summarize — do not touch the history.
        return CompactionResult(hist)

    old, tail = hist[:drop_n], hist[drop_n:]
    facts, facts_file = flush_facts(old, home_dir=home_dir, extractor=extractor)
    build = summarizer or default_summarizer
    summary = build(old, facts)
    checkpoint = ModelRequest(parts=[SystemPromptPart(content=summary)])
    return CompactionResult(
        history=[checkpoint, *tail],
        summary=summary,
        facts=facts,
        facts_file=facts_file,
        compacted=True,
    )


if __name__ == "__main__":  # pragma: no cover — runnable self-check (no LLM)
    import tempfile

    def _turn(i: int) -> list[ModelMessage]:
        from pydantic_ai.messages import ModelResponse, TextPart

        return [
            ModelRequest(parts=[UserPromptPart(content=f"вопрос {i}: пользователь говорит про тему {i}")]),
            ModelResponse(parts=[TextPart(content=f"ответ {i}")]),
        ]

    hist = [m for i in range(10) for m in _turn(i)]
    assert len(hist) == 20 and estimate_size(hist) > 0

    # Over threshold (20 > max_messages=12) -> compacted.
    res = compact_history(hist, home_dir=Path(tempfile.gettempdir()))
    assert res.compacted and len(res.history) == 1 + DEFAULT_PROTECT_LAST_N
    assert res.history[1:] == hist[-DEFAULT_PROTECT_LAST_N:], "хвост должен остаться нетронутым"
    head = res.history[0]
    assert isinstance(head, ModelRequest) and any(
        isinstance(p, SystemPromptPart) and _CHECKPOINT_MARKER in p.content for p in head.parts
    ), "checkpoint должен быть SystemPromptPart с маркером"
    assert res.facts and res.facts_file is not None and res.facts_file.exists(), "факты должны быть сброшены в файл"

    # Under threshold -> no-op, history untouched.
    res2 = compact_history(hist[:6])
    assert not res2.compacted and res2.history == hist[:6]

    # protect_last_n >= len(history) -> no-op.
    res3 = compact_history(hist, protect_last_n=len(hist))
    assert not res3.compacted

    print("context ok")
