# Privacy Policy

Last updated: August 21, 2026

Aloth is a personal AI assistant that runs locally on your computer. We minimize data collection: the application does not transfer information to third-party systems unless explicitly initiated by you.

## What is stored locally

- **Settings, memory and sessions** — in the `~/.aloth` folder on your computer: configuration, chat history, facts about you, skills, logs.
- **API keys** — stored in the Windows Credential Manager; they never leave your machine.
- **Audit log** — a local record of agent actions.

## What is sent over the network

- **Conversations with the model** — your messages and responses are sent to the LLM provider you configured (DeepSeek by default), whose API key you entered in settings. This happens only when you actively use the assistant: you choose the provider and supply the key yourself.
- **Web search** — if you use web search, queries go to the configured search service (DuckDuckGo by default).

The program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.

## Updates

Update checks contact the update server (GitHub Releases) only to report whether a new version is available.

## Contact

For privacy questions: [open an issue](https://github.com/Lutkovtime/Aloth/issues).
