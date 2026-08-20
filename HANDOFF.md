# Aloth — HANDOFF (20.08.2026, вечер)

> Новая сессия: прочитай этот файл + `C:/Hermes/Brain-vault/Projects/aloth-plan.md`
> (источник правды — весь план продукта). Продолжай с «Следующий шаг» ниже.

## Что это

Aloth (Amazing Sloth) — open-source AI-агент «для всех» (от бабушки до senior),
MIT, Windows+Linux. Референсы: Hermes (наш стек) + OpenClaw. Строим с нуля, НЕ форк.

## Код

`C:/Hermes/Aloth` — uv-проект, src-layout, Python 3.11, pydantic-ai 2.32.1.

```
src/aloth/
  __init__.py   версия 0.1.0
  home.py       дом ~/.aloth (config/data/skills/backups/logs/runtime), self-check есть
  sessions.py   SQLite + FTS5 (сессии, сообщения, поиск), self-check есть
  core.py       Agent('deepseek:deepseek-chat') + тул current_time
  cli.py        aloth chat "...", aloth home, aloth search "query"
pyproject.toml  entry point: aloth = aloth.cli:main, MIT
```

## Статус

- ✅ Пакет собирается, entry point работает, self-check'и home/sessions проходят.
- ⚠️ **Боевой чат НЕ проверен** после фикса: тулы в PydanticAI 2.32 требуют
  `ctx: RunContext[None]` первым аргументом (был TypeError, исправлено).
- Проект НЕ закоммичен в git (только uv-инициализация), GitHub не создан.

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

1. Боевой тест: `uv run aloth chat "Привет! Который час по UTC?"` — убедиться, что loop + тул работают.
2. git init commit (ветка main, .gitignore уже есть), GitHub private repo (gh авторизован).
3. По чеклисту плана (Процесс разработки): тулы (память/файлы/терминал/веб) → evals →
   GUI PySide6 → безопасность (per-tool deny-by-default) → установщик (PyInstaller onedir + Inno).

## Нюансы (копать не заново)

- PydanticAI 2.32.1: тулы = `@agent.tool` + `ctx: RunContext[None]`; модель строкой
  `deepseek:deepseek-chat` (known model), ключ из env DEEPSEEK_API_KEY.
- uv_build жёстко ждёт src-layout (`src/aloth/__init__.py`) — корневой пакет не соберётся.
- Entry point в pyproject: `aloth = "aloth.cli:main"`.
- Nous inference: /v1/models требует браузерный UA (Cloudflare 1010 на urllib без него).
