# Aloth — HANDOFF (20.08.2026, вечер)

> Новая сессия: прочитай этот файл + `C:/Hermes/Brain-vault/Projects/aloth-plan.md`
> (источник правды — весь план продукта). Продолжай с «Следующий шаг» ниже.

## Что это

Aloth (Amazing Sloth) — open-source AI-агент «для всех» (от бабушки до senior),
MIT, Windows+Linux. Референсы: Hermes (наш стек) + OpenClaw. Строим с нуля, НЕ форк.

## Код

`C:/Hermes/Aloth` — uv-проект, src-layout, Python 3.11, pydantic-ai 2.32.1.
GitHub: `Lutkovtime/Aloth` (private, ветка main, push настроен).

```
src/aloth/
  __init__.py   версия 0.1.0
  home.py       дом ~/.aloth (config/data/skills/backups/logs/runtime), self-check
  sessions.py   SQLite + FTS5 (сессии, сообщения, поиск), self-check
  memory.py     память L1: факты (add/forget/all), self-check
  files.py      файловые тулы, только в пределах дома, escape-safe, self-check
  web.py        веб-поиск (ddgs, без ключей), self-check
  core.py       Agent + тулы: current_time, memory_add/forget, file_read/write, search_web
  cli.py        aloth chat "...", aloth home, aloth search "query"
pyproject.toml  entry point: aloth = aloth.cli:main, MIT; deps: pydantic-ai, ddgs
```

## Статус

- ✅ Боевой чат проверен: loop + все тулы работают (время, память, файлы, веб).
- ✅ Память L1: факты в системном промпте, memory_add/forget — работают.
- ✅ Файлы: read/write только в ~/.aloth, ../ и absolute вне дома отклоняются.
- ✅ Веб: search_web через ddgs (без API-ключей).
- ✅ GitHub: private Lutkovtime/Aloth, ветка main, первые коммиты запушены.
- ⚠️ Нюанс: DeepSeek flash сам НЕ вызывает тул без явной просьбы («запомни» без
  «вызови тул» → отвечает «запомнил», но не вызывает). Для продакшена — думать
  (лучший системный промпт / tool_choice / guardrails). Не баг, а особенность модели.

## Запуск

```bash
cd /c/Hermes/Aloth
export DEEPSEEK_API_KEY=<из .env Hermes>
uv run aloth chat "привет"
```

## Модели-стратегия (утверждена)

flash (наш DeepSeek-ключ) — рутина; qwen3-coder ($0.24/0.8 через Nous) — код по ТЗ;
claude-sonnet-5 ($1.6/8) — архитектура/рефакторинг; claude-opus-5 ($4/20) — только тупики.
Через Nous: `hermes -z "..." -m "anthropic/claude-sonnet-5" --provider nous`.
Балансы: DeepSeek ~$5.6, Nous ~$20.

## Следующий шаг

По чеклисту плана (Процесс разработки): тулы готовы (память/файлы/веб) →
1. **Evals** — реальные задачи с проверяемыми исходами для имеющихся тулов
   (память: запомнил→в новой сессии видит; файлы: запись→чтение; веб: поиск→ссылки).
   Простейший eval-runner: список кейсов {prompt, проверка}, прогон через aloth chat,
   отчёт pass/fail.
2. **Терминал** — НЕ добавлять без системы одобрений (per-tool deny-by-default,
   профили доверия). Это следующий блок после evals — вместе с безопасностью.
3. GUI PySide6 → безопасность → установщик (PyInstaller onedir + Inno).

## Нюансы (копать не заново)

- PydanticAI 2.32.1: тулы = `@agent.tool` + `ctx: RunContext[None]`; модель строкой
  `deepseek:deepseek-chat` (known model), ключ из env DEEPSEEK_API_KEY.
- SQLite-соединение для тулов — `check_same_thread=False` (тулы в event-loop thread).
- Path в файловых тулах — Windows-сепаратор: нормализовать `\` → `/` при выводе.
- uv_build жёстко ждёт src-layout (`src/aloth/__init__.py`).
- Entry point в pyproject: `aloth = "aloth.cli:main"`.
- Nous inference: /v1/models требует браузерный UA (Cloudflare 1010 на urllib без него).
