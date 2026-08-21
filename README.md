# Aloth

A local-first AI assistant for Windows — chat with an AI agent from a desktop app or your terminal. Your data stays on your machine.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)
![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey)
![Release](https://img.shields.io/github/v/release/Lutkovtime/Aloth)

> **Early stage:** Aloth is under active development. Features and CLI flags may change between versions.

## Features

- **Desktop chat** — GUI with chat, memory, skills and settings
- **Terminal CLI** — `aloth chat "..."`, `aloth setup`, `aloth security`
- **Local data** — everything lives in `~/.aloth`; backup is copying one folder
- **Memory** — facts about you stay in context across sessions
- **Skills** — plain `.md` files the agent follows
- **Security first** — deny-by-default tool permissions, human approval (HITL), full audit log
- **Bring your own model** — OpenAI-compatible providers (DeepSeek by default)
- **Web search** — via DuckDuckGo

## Installation

### Installer

Download `Aloth-Setup-*.exe` from [Releases](https://github.com/Lutkovtime/Aloth/releases) and run it — no admin rights required.

### From source

```bash
git clone https://github.com/Lutkovtime/Aloth.git
cd Aloth
uv sync
export DEEPSEEK_API_KEY=sk-...
uv run aloth chat "hello"
```

## Quick start

```bash
aloth setup              # enter your API key, choose trust profile
aloth gui                # desktop app
aloth chat "hello"       # chat from the terminal
aloth security list      # which tools are enabled
```

## Status

Early development. The current release is **0.1.x**: usable for basic chat, memory and tool use, but expect rough edges. Planned work: terminal REPL, first-run wizard, file-based memory, signed releases.

## FAQ

**What state is the project in?**
Alpha. It works for basic chat, memory and tool use; interfaces may change between versions.

**Will Aloth send my data anywhere?**
Only to the LLM provider you configure — you supply the API key yourself. Conversations and data stay on your machine; see the [privacy policy](docs/privacy-policy.md).

**How do I remove it?**
The uninstaller asks whether to delete your data (`~/.aloth`) or keep it.

## Development

```bash
uv sync
uv run python -m aloth.evals   # run evals
```

Build instructions: `docs/build.md`.

## Code signing policy

Free code signing provided by [SignPath.io](https://signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

- **Signed artifacts**: official releases (installer and executables) from GitHub Releases.
- **Team**: solo maintainer [Lutkovtime](https://github.com/Lutkovtime) — Author / Reviewer / Approver. Every release is manually approved before signing.
- **Verification**: binaries are built from the source in this repository; a signature confirms the binary matches the tagged source.
- **Privacy**: see the [privacy policy](docs/privacy-policy.md).

## License

MIT — see [LICENSE](LICENSE).
