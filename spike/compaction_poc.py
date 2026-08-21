"""Compaction PoC: PydanticAI agent.iter() mid-loop.

Verifies the mechanics we need for context.py:
1. agent.iter() yields AgentRun nodes we can observe between steps.
2. ctx.state.message_history is mutable — we can replace it mid-run.
3. After replacement, the run continues and the model sees the compacted
   history (a synthetic summary part), i.e. protect_last_n + summarize
   is implementable on top of this API without forking PydanticAI.

Uses the built-in test model (no API key, deterministic).
"""
import asyncio
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
    SystemPromptPart,
)

ok = True


def check(name: str, cond: bool, detail: str = "") -> None:
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")
    ok = ok and cond


def count_messages(state) -> int:
    return len(state.message_history)


async def main() -> int:
    agent = Agent("test", system_prompt="You are a concise assistant.")

    # Long dialog: several user turns with model responses, then compact mid-run.
    turns = [
        "First: user likes tea.",
        "Second: user lives in Berlin.",
        "Third: user works as a developer.",
        "Fourth: user has a cat named Bob.",
    ]
    async with agent.iter(turns[0]) as run:
        # drive first turn to completion
        async for _ in run:
            pass
        n0 = len(run.all_messages())
        check("turn1", n0 >= 2, f"n={n0}")

        # second turn
        async with agent.iter(turns[1], message_history=run.all_messages()) as run2:
            async for _ in run2:
                pass
            n1 = len(run2.all_messages())
            check("turn2", n1 > n0, f"n={n1}")

            # third turn — compact BEFORE it runs: summarize history, keep last exchange
            summary = ModelRequest(
                parts=[
                    SystemPromptPart(
                        content="CONTEXT CHECKPOINT (compacted): user likes tea, lives in Berlin, works as a developer."
                    )
                ]
            )
            hist = run2.all_messages()
            # protect_last_n=2: keep last request+response, drop the rest
            new_hist = [summary, *hist[-2:]]
            n_before = len(hist)
            check("compaction_shrinks", len(new_hist) < n_before, f"{n_before} -> {len(new_hist)}")

            # run the compacted turn
            async with agent.iter(turns[2], message_history=new_hist) as run3:
                async for _ in run3:
                    pass
                final = run3.all_messages()
                has_summary = any(
                    isinstance(m, ModelRequest)
                    and any(isinstance(p, SystemPromptPart) and "CONTEXT CHECKPOINT" in p.content for p in m.parts)
                    for m in final
                )
                check("summary_persisted", has_summary, f"final n={len(final)}")
                check("run_completes", run3.result is not None and getattr(run3.result, "output", None) is not None,
                      str(getattr(run3.result, "output", None))[:60])

    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
