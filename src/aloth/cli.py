"""Aloth CLI — `aloth chat "..."`, `aloth home`, `aloth sessions search "..."`."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from aloth import config
from aloth.core import build_agent
from aloth.files import FileTools
from aloth.home import ensure_home, home_dir
from aloth.memory import MemoryStore
from aloth.security import SecurityPolicy
from aloth.sessions import SessionStore
from aloth.shell import Shell


def _store() -> SessionStore:
    home = ensure_home()
    return SessionStore(home / "data" / "sessions.db")


def _mem() -> MemoryStore:
    home = ensure_home()
    return MemoryStore(home / "data" / "memory.db")


def _cmd_chat(args: argparse.Namespace) -> int:
    if not args.message:
        print("Пустое сообщение. Пример: aloth chat \"привет\"", file=sys.stderr)
        return 2

    home = ensure_home()
    settings = config.load(home)
    if not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ALOTH_API_KEY")
            or settings.api_key):
        print("Запусти aloth setup чтобы ввести API-ключ", file=sys.stderr)
        return 2

    store = _store()
    mem = _mem()
    files = FileTools(home)
    shell = Shell(profile=args.profile or settings.profile)
    policy = SecurityPolicy.load(home)
    agent = build_agent(model=args.model, memory=mem, files=files, shell=shell,
                        security=policy, skills_dir=home / "skills",
                        api_key=settings.api_key or None)
    sid = args.session or store.create_session()

    async def run() -> str:
        # Feed history so the agent keeps context across runs.
        history = store.history(sid, limit=args.history)
        prompt = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        prompt = f"{prompt}\nuser: {args.message}" if history else args.message
        result = await agent.run(prompt)
        return result.data if hasattr(result, "data") else str(result)

    store.add_message(sid, "user", args.message)
    try:
        reply = asyncio.run(run())
    finally:
        policy.close()
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


def _cmd_gui(args: argparse.Namespace) -> int:
    from aloth.gui import main as gui_main
    argv = ["--profile", args.profile] if args.profile else []
    return gui_main(argv)


def _cmd_setup(_: argparse.Namespace) -> int:
    home = ensure_home()
    current = config.load(home)
    key = input("DeepSeek API key: ").strip() or current.api_key
    profile = input(
        f"Профиль доверия ({'/'.join(config.PROFILES)}, default: {current.profile}): "
    ).strip() or current.profile
    try:
        config.save(home, config.Settings(api_key=key, profile=profile))
    except ValueError as e:
        print(f"ошибка: {e}", file=sys.stderr)
        return 2
    print("готово")
    return 0


def _cmd_security(args: argparse.Namespace) -> int:
    policy = SecurityPolicy.load(ensure_home())
    if args.action == "list":
        for name, entry in policy.matrix().items():
            state = "on" if entry["enabled"] else "off"
            print(f"{name:16} {state:4} autoApprove={entry['autoApprove']}")
    elif args.action == "set":
        if args.tool not in policy.matrix():
            print(f"неизвестный тул: {args.tool}", file=sys.stderr)
            policy.close()
            return 2
        policy.set_tool(args.tool, args.enabled == "on")
        policy.save()
        print(f"{args.tool}: {'on' if args.enabled else 'off'}")
    elif args.action == "audit":
        for row in policy.recent():
            print(f"{row['ts']} {row['tool']:12} "
                  f"{'OK ' if row['allowed'] else 'BLOCK'} {row['args'][:100]}")
    policy.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="aloth", description="Aloth (Amazing Sloth)")
    p.add_argument("--model", default="deepseek:deepseek-chat")
    p.add_argument("--profile", default=None,
                   choices=["readonly", "full"],
                   help="профиль доверия для shell (default: из настроек или readonly)")
    sub = p.add_subparsers(dest="cmd", required=True)

    chat = sub.add_parser("chat", help="поговорить с агентом")
    chat.add_argument("message")
    chat.add_argument("--session")
    chat.add_argument("--history", type=int, default=10)
    chat.set_defaults(fn=_cmd_chat)

    setup = sub.add_parser("setup", help="первый запуск: API-ключ и профиль доверия")
    setup.set_defaults(fn=_cmd_setup)

    home = sub.add_parser("home", help="показать дом агента")
    home.set_defaults(fn=_cmd_home)

    gui = sub.add_parser("gui", help="графический интерфейс (чат)")
    gui.set_defaults(fn=_cmd_gui)

    sec = sub.add_parser("security", help="матрица тулов и audit-log")
    sec_sub = sec.add_subparsers(dest="action", required=True)
    sec_sub.add_parser("list").set_defaults(fn=_cmd_security, action="list")
    sec_set = sec_sub.add_parser("set", help="включить/выключить тул")
    sec_set.add_argument("tool")
    sec_set.add_argument("enabled", choices=["on", "off"])
    sec_set.set_defaults(fn=_cmd_security, action="set")
    sec_sub.add_parser("audit", help="последние вызовы").set_defaults(
        fn=_cmd_security, action="audit")

    search = sub.add_parser("search", help="поиск по истории сессий")
    search.add_argument("query")
    search.set_defaults(fn=_cmd_search)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
