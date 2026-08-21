# Aloth — Evals Baseline (Фаза 0 → Фаза 1)

> Зафиксировано 21.08.2026, до начала Фазы 1. От этого набора считаются цели.
> Прогон: `ALOTH_HOME="$LOCALAPPDATA/Temp/aloth-eval-$$" DEEPSEEK_API_KEY=... uv run python -m aloth.evals`
> (не `$(mktemp -d)` — MSYS-путь `/tmp/...` ломается в Windows-pathlib как `C:\tmp\...`; scratch для нативных тулов — только `$LOCALAPPDATA/Temp`)

## Результат: 12/12 PASS (после Фазы 1, 21.08)

### LLM-кейсы (7)

| # | Кейс | Что проверяет | Статус |
|---|------|---------------|--------|
| 1 | `time_tool` | current_time тул, год в ответе | ✅ |
| 2 | `memory_save_and_see` | memory_add вызывается, факт подтверждается | ✅ |
| 3 | `memory_persists_new_session` | факт из кейса 2 виден в новой сессии | ✅ |
| 4 | `file_write_read` | file_write/file_read внутри дома | ✅ |
| 5 | `web_search_returns_links` | search_web (ddgs) возвращает результаты | ✅ |
| 6 | `shell_readonly_blocks_dangerous` | readonly профиль блокирует rm -rf | ✅ |
| 7 | `hitl_denied` | autoApprove=false + отказ → тул отменён, запись в audit | ✅ |

### Unit-кейсы (5, Фаза 1.7 — без LLM, детерминированные)

| # | Кейс | Что проверяет |
|---|------|---------------|
| 8 | `compaction_preserves_facts` | 20 сообщений → checkpoint, факт из середины сохранён, хвост цел |
| 9 | `provider_resolve_and_discover` | resolve пресетов/произвольного провайдера, discover на MockTransport |
| 10 | `secrets_keyring_roundtrip` | set/get/delete через keyring (backend=keyring) |
| 11 | `migrate_moves_key_out_of_settings` | api_key уходит из settings.json в keyring, бэкап создан |
| 12 | `health_reports` | run_health возвращает отчёт в обоих уровнях |

## Цели по фазам (из карты)

- **Ф1**: 12/12 ✅ (достигнуто)
- **Ф2–Ф5**: держать 12/12 после каждого регресс-гейта.

## Примечания

- Модель: `deepseek:deepseek-chat` (flash), профиль readonly, изолированный
  ALOTH_HOME — тесты не касаются реальных данных.
- Известный нюанс (из HANDOFF): flash сам не вызывает тул без явной просьбы
  («запомни» без «вызови тул»). В evals промпты явно требуют вызов.
- LLM-кейсы флаки (недетерминизм): кейс 3 усилен явным указанием искать
  факты в системном промпте; кейс 4 устойчив к чтению каталогов/бинарных
  файлов (тулы возвращают «ошибка: …», не роняют диалог).
- Найдено при прогоне (починено): `shell.py` — `encoding="utf-8", errors="replace"`
  (Windows-консоль выдаёт cp1251/cp866 → UnicodeDecodeError валил run_command);
  `files.py` read — `errors="replace"`; `core.py` file_read/file_write — ловят
  OSError и возвращают сообщение вместо исключения.
