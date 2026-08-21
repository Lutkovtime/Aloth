# Аудит «одного дома» (ЗАДАЧА 1.9)

**Цель:** зафиксировать, пишет/читает ли приложение что-либо вне `~/.aloth`
(принцип Ц3: вся жизнь агента — в одном доме, ничего в реестре/AppData/Documents).
**Метод:** grep по `src/aloth/*.py` на `open(`, `Path(`, `os.environ`, `APPDATA`,
`LOCALAPPDATA`, `expanduser`, `mkdir`, `write_text`, `sqlite3.connect` + ручной
просмотр файлов. **Дата:** 2026-08-21, коммит `c6019ba`.
**Статус:** отчёт без правок кода (нарушения решает лид).
**Примечание:** во время аудита лид параллельно вёл рефакторинг (config.py,
cli.py, sessions.py, новые secrets.py/migrate.py/context.py/providers.py) —
таблица отражает состояние на момент фиксации.

## Таблица: файл → что пишет/читает → путь → внутри дома?

| Файл | Что пишет/читает | Путь | Внутри дома? |
|---|---|---|---|
| `cli.py` | читает env `DEEPSEEK_API_KEY` / `ALOTH_API_KEY`; ключ через `secrets.get_api_key` | `os.environ` (чтение), Credential Manager | ✅ записи на диск нет |
| `config.py` | `settings.json` (profile, ui_level, version — без секретов) | `~/.aloth/config/settings.json` | ✅ |
| `context.py` `flush_facts` | checkpoint-файлы фактов | `<home_dir>/.aloth/context/checkpoint-*.md` | ⚠️ см. примечание 4 |
| `core.py` | читает env-ключи; `os.environ.setdefault` в процессе | `os.environ` (в памяти) | ✅ диска не касается |
| `evals.py` | `_hitl_case`: MemoryStore/SecurityPolicy | `~/.aloth/data/*.db` | ✅ но живой дом, не throwaway (прим. 3) |
| `files.py` | read/write по home-относительным путям, escape-защита | `~/.aloth/**` | ✅ выход блокируется |
| `gui.py` | skills/*.md, settings.json, memory.db, sessions.db | `~/.aloth/...` | ✅ |
| `gui.py:101` `_icon()` | **читает** logo.ico/png из каталога приложения | `parents[2]/assets` или `_MEIPASS` | ⚠️ вне дома, но только чтение ресурсов |
| `home.py` | создаёт подкаталоги дома | `~/.aloth/{config,data,skills,backups,logs,runtime}` | ✅ |
| `logging.py` (новый, 1.5) | `aloth.log` + ротация 1 МБ × 5 | `~/.aloth/logs/aloth.log(.1..5)` | ✅ |
| `health.py` (новый, 1.6) | читает `settings.json` + ключ, пишет предупреждения в лог | `~/.aloth/...` | ✅ |
| `memory.py` | `memory.db` (SQLite) | `~/.aloth/data/memory.db` | ✅ |
| `migrate.py` | бэкап дома, миграция ключа, правка settings.json и data/*.db | `~/.aloth/backups/<ts>`, `~/.aloth/data/...` | ✅ |
| `providers.py` | env-переменные (чтение/установка в процессе) | `os.environ` (в памяти) | ✅ диска не касается |
| `secrets.py` | **пишет API-ключ в Windows Credential Manager (keyring)**; fallback — `settings.json` | Credential Manager / `~/.aloth/config/settings.json` | ⚠️ Credential Manager вне дома, by design (прим. 1) |
| `security.py` | `security.json` + `audit.db` (SQLite) | `~/.aloth/config/security.json`, `~/.aloth/data/audit.db` | ✅ |
| `sessions.py` | `sessions.db` (SQLite) | `~/.aloth/data/sessions.db` | ✅ |
| `shell.py` | `subprocess` произвольных команд | куда угодно (пользовательские команды) | ⚠️ by design (прим. 2) |
| `web.py` | сеть (DuckDuckGo) | — | ✅ диска не касается |

## Вердикт

**Нарушений «одного дома» в файловой системе не найдено.** Все SQLite-базы
(`memory.db`, `audit.db`, `sessions.db`), конфиги (`settings.json`,
`security.json`) и логи — внутри `~/.aloth`. Два канала, уводящих наружу —
Credential Manager и `shell.py` — оба осознанные дизайн-решения, не случайные
записи. Файловых следов в `AppData`/`Documents`/реестре нет.

## Примечания (на заметку лиду, НЕ правки)

1. **`secrets.py` → Credential Manager (keyring)** — единственная запись вне
   `~/.aloth`, но это хранилище секретов ОС, а не пользовательские файлы;
   решение лида. Fallback-путь при недоступном keyring пишет в
   `~/.aloth/config/settings.json` (внутри дома) с флагом
   `api_key_plaintext_fallback=true`.
2. **`shell.py`** — единственный канал записи в произвольное место ФС, закрыт
   политикой доступа (readonly по умолчанию, `_ALWAYS_BLOCKED` для
   `rm/mv/dd/...`).
3. **`evals.py:_hitl_case`** — использует `ensure_home()` (реальный дом), хотя
   docstring обещает throwaway-дом. Кандидат: задавать `ALOTH_HOME` во
   временную папку в тестовом прогоне.
4. **`context.py:flush_facts`** — семантическое расхождение: параметр
   `home_dir` трактуется как *родитель* дома (пишет `<home_dir>/.aloth/context/`),
   тогда как `aloth.home.home_dir()` возвращает сам `~/.aloth`. Если вызвать с
   `home_dir()`, получится вложенный `~/.aloth/.aloth/context/`. В обоих случаях
   путь остаётся внутри пользовательского дома, но вне канонического набора
   подкаталогов — выровнять с `home.py` (передавать родителя или убрать
   `/.aloth` из шаблона). Self-check пишет в `tempfile.gettempdir()` — тест, ок.
5. **`gui.py:101`** — `_icon()` читает иконку из каталога установки (`_MEIPASS`
   при freeze, иначе `parents[2]/assets`). Чтение ресурсов приложения, не
   пользовательских данных; в дом не пишет.
6. **`tempfile.TemporaryDirectory`** в self-check'ах всех модулей (включая новые
   `logging.py`, `health.py`, `secrets.py`) — пишет вне дома, но эфемерно и
   только в `__main__` — приемлемо.
7. **Env-переменные** (`DEEPSEEK_API_KEY`, `ALOTH_API_KEY`, `ALOTH_HOME`) —
   только чтение/в-процессе; `ALOTH_HOME` легально переносит дом (фича).

## Проверено

- `uv run python -m aloth.logging` → `logging ok`
- `uv run python -m aloth.health` → `health ok`
