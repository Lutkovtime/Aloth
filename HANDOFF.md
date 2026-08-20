# Aloth — HANDOFF (20.08.2026, вечер)

> Новая сессия: прочитай этот файл + `C:/Hermes/Brain-vault/Projects/aloth-plan.md`
> (источник правды — весь план продукта). Продолжай с «Следующий шаг» ниже.
> Проект: **C:/Projects/Aloth** (перенесён из C:/Hermes/Aloth 21.08).

## Что это

Aloth (Amazing Sloth) — open-source AI-агент «для всех» (от бабушки до senior),
MIT, Windows+Linux. Референсы: Hermes (наш стек) + OpenClaw. Строим с нуля, НЕ форк.

## Код

`C:/Projects/Aloth` — uv-проект, src-layout, Python 3.11, pydantic-ai 2.32.1.
GitHub: `Lutkovtime/Aloth` (private, ветка main, push настроен).

```
src/aloth/
  __init__.py   версия 0.1.0
  home.py       дом ~/.aloth (config/data/skills/backups/logs/runtime), self-check
  sessions.py   SQLite + FTS5 (сессии, сообщения, поиск), self-check
  memory.py     память L1: факты (add/forget/all), self-check
  files.py      файловые тулы, только в пределах дома, escape-safe, self-check
  web.py        веб-поиск (ddgs, без ключей), self-check
  shell.py      терминал: deny-by-default, профили readonly/full, self-check
  core.py       Agent + тулы: current_time, memory_add/forget, file_read/write,
                search_web, run_command
  cli.py        aloth chat "...", aloth home, aloth search "query"; --profile
  evals.py      eval-runner: 6 кейсов, прогон в изолированном ALOTH_HOME
pyproject.toml  entry point: aloth = aloth.cli:main, MIT; deps: pydantic-ai, ddgs
```

## Статус

- ✅ Боевой чат проверен: loop + все тулы работают.
- ✅ Память L1: факты в системном промпте, memory_add/forget.
- ✅ Файлы: read/write только в ~/.aloth, ../ и absolute вне дома отклоняются.
- ✅ Веб: search_web через ddgs (без API-ключей).
- ✅ Терминал: run_command с профилями доверия. readonly — только безопасные
  команды; full — всё кроме всегда-запрещённых (rm/mv/sudo/...); deny wins.
  Флаг: `aloth --profile full chat "..."` (глобальный, до подкоманды).
- ✅ Evals: `ALOTH_HOME=$(mktemp -d) DEEPSEEK_API_KEY=... uv run python -m aloth.evals`
  — 6/6 pass (время/память/файлы/веб/shell-блокировка).
- ✅ GitHub: private Lutkovtime/Aloth, ветка main.
- ⚠️ Нюанс: DeepSeek flash сам НЕ вызывает тул без явной просьбы («запомни» без
  «вызови тул» → отвечает «запомнил», но не вызывает). Для продакшена — думать
  (лучший системный промпт / tool_choice / guardrails).

## Запуск

```bash
cd /c/Hermes/Aloth
export DEEPSEEK_API_KEY=<из .env Hermes>
uv run aloth chat "привет"
uv run aloth --profile full chat "покажи дату"
```

## Модели-стратегия (утверждена)

flash (наш DeepSeek-ключ) — рутина; qwen3-coder ($0.24/0.8 через Nous) — код по ТЗ;
claude-sonnet-5 ($1.6/8) — архитектура/рефакторинг; claude-opus-5 ($4/20) — только тупики.
Через Nous: `hermes -z "..." -m "anthropic/claude-sonnet-5" --provider nous`.
Балансы: DeepSeek ~$5.6, Nous ~$20.

- ✅ Безопасность: security.py — per-tool матрица {enabled, autoApprove}
  (config/security.json, deny-by-default: неизвестный тул = выключен),
  audit-log каждого вызова (data/audit.db), CLI `aloth security list|set|audit`.
  shell.py: canonicalize() срезает timeout/nohup/env-префиксы — иначе
  `timeout 5 rm -rf /` обходит deny-список.
- ✅ GUI PySide6: `aloth gui` — чат + список сессий (создание, переключение,
  история, агент в QThread, UI не замирает). Offscreen smoke + живой ответ
  через AgentWorker проверены. GUI прогон: evals 6/6.
- ✅ Вкладки GUI (20.08): «Чат» | «Память» (факты L1: список/добавить/забыть) |
  «Навыки» (редактор ~/.aloth/skills/*.md) | «Настройки» (матрица security.json:
  enabled/autoApprove + сохранение). Проверено offscreen smoke.
- ✅ HITL: autoApprove=false РЕАЛЬНО спрашивает — QMessageBox в GUI
  (AgentWorker: approval_requested signal + threading.Event, approver в
  build_agent); отказ → тул «отменено пользователем» + запись в audit
  (allowed=0). CLI работает без approver (как раньше). Evals 7/7 (hitl_denied).
- ✅ Навыки работают: *.md из ~/.aloth/skills/ инжектятся в system_prompt
  («Навыки (инструкции пользователя):»), подхват и в CLI, и в GUI.
- ✅ Онбординг: `aloth setup` (интерактивный ввод API-ключа + профиля
  доверия, config/settings.json); GUI при первом запуске — диалог
  (ключ + профиль); chat без ключа → подсказка «aloth setup», exit 2.
  api_key в build_agent: env → settings (через setdefault).
- ✅ Установщик: PyInstaller onedir (dist/aloth/ CLI + dist/aloth-gui/
  GUI, --copy-metadata genai_prices pydantic_ai_slim mcp + --exclude-module
  logfire — без них frozen падает PackageNotFoundError/OSError) +
  installer.iss (Inno 6, PrivilegesRequired=lowest) → Aloth-Setup-0.1.0.exe.
  Проверено: тихая установка в чистый каталог, aloth.exe --help,
  aloth-gui.exe жив (offscreen). Сборка: docs/build.md. README + LICENSE (MIT).
- ✅ UX-фиксы (21.08): GUI — трей (close→hide, меню: открыть/выход),
  AppUserModelID, иконка окна, QSS тёплая коричнево-золотая тема;
  онбординг-мастер: 3 кнопки (Всё, что есть → profile=full+все тулы /
  Я выберу сам → readonly / Голое ядро → без run_command,file_write) +
  «Пропустить» + «Где взять ключ?» (DeepSeek) + «Позже»; API-ключ
  редактируется во вкладке «Настройки». installer.iss: уникальный AppId,
  выбор пути (DisableDirPage=no), ярлыки GUI + «Aloth (терминал)»
  (scripts/aloth.cmd) + Удалить, publisher, иконка setup; деинсталлятор
  спрашивает про удаление ~/.aloth ([Code] DelTree, default Нет).

## Следующий шаг

1. **Бета-тест Саши** — установить Aloth-Setup-0.1.0.exe: онбординг
   (3 кнопки → ключ → профиль), чат через DeepSeek, трей, терминал-ярлык,
   настройки, удаление (с данными).
2. По фидбеку — правки; потом публикация (public + Releases).
3. Из плана дальше (не для первого теста): RAG-память (ChromaDB/sqlite-vec),
   стиль/личность (SOUL.md-аналог во вкладке), локальные модели/OpenRouter,
   апдейтер с подписью, Linux (.deb/AppImage).

## Нюансы (копать не заново)

- PydanticAI 2.32.1: тулы = `@agent.tool` + `ctx: RunContext[None]`; модель строкой
  `deepseek:deepseek-chat` (known model), ключ из env DEEPSEEK_API_KEY.
- SQLite-соединение для тулов — `check_same_thread=False` (тулы в event-loop thread).
- Path в файловых тулах — Windows-сепаратор: нормализовать `\` → `/` при выводе.
- uv_build жёстко ждёт src-layout (`src/aloth/__init__.py`).
- Entry point в pyproject: `aloth = "aloth.cli:main"`.
- Nous inference: /v1/models требует браузерный UA (Cloudflare 1010 на urllib без него).
