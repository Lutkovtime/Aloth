"""Aloth CLI — `aloth chat "..."`, `aloth home`, `aloth sessions search "..."`."""

from __future__ import annotations

import argparse
import asyncio
import sys

from aloth.core import build_agent
from aloth.home import ensure_home, home_dir
from aloth.sessions import SessionStore


def _store() -> SessionStore:
    home = ensure_home()
    return SessionStore(home / "data" / "sessions.db")


def _cmd_chat(args: argparse.Namespace) -> int:
    if not args.message:
        print("Пустое сообщение. Пример: aloth chat \"привет\"", file=sys.stderr)
        return 2

    store = _store()
    agent = build_agent(model=args.model)
    sid = args.session or store.create_session()

    async def run() -> str:
        # Feed history so the agent keeps context across runs.
        history = store.history(sid, limit=args.history)
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        prompt = f"{prompt}\nuser: {args.message}" if history else args.message
        result = await agent.run(prompt)
        return result.data if hasattr(result, "data") else str(result)

    store.add_message(sid, "user", args.message)
    reply = asyncio.run(run())
    store.add_message(sid, "assistant", reply)

    print(reply)
    print(f"\n[session {sid}]", file=sys.stderr)
    return 0


def _cmd_home(_: argparse.Namespace) -> int:
    print(home_dir())
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    store = _store()
    for row in store.search(args.query):
        print(f"[{row['session_id']}] {row['role']}: {row['content'][:120]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aloth", description="Aloth (Amazing Sloth)")
    p.add_argument("--model", default="deepseek:deepseek-chat")
    sub = p.add_subparsers(dest="cmd", required=True)

    chat = sub.add_parser("chat", help="поговорить с агентом")
    chat.add_argument("message")
    chat.add_argument("--session")
    chat.add_argument("--history", type=int, default=10)
    chat.set_defaults(fn=_cmd_chat)

    home = sub.add_parser("home", help="показать дом агента")
    home.set_defaults(fn=_cmd_home)

    search = sub.add_parser("search", help="поиск по истории сессий")
    search.add_argument("query")
    search.set_defaults(fn=_cmd_search)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
