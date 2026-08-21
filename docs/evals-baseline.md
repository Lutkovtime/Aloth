# Aloth — Evals Baseline (Фаза 0)

> Зафиксировано 21.08.2026, до начала Фазы 1. От этого набора считаются цели.
> Прогон: `ALOTH_HOME=$(mktemp -d) DEEPSEEK_API_KEY=... uv run python -m aloth.evals`

## Результат: 7/7 PASS

| # | Кейс | Что проверяет | Статус |
|---|------|---------------|--------|
| 1 | `time_tool` | current_time тул, год в ответе | ✅ |
| 2 | `memory_save_and_see` | memory_add вызывается, факт подтверждается | ✅ |
| 3 | `memory_persists_new_session` | факт из кейса 2 виден в новой сессии | ✅ |
| 4 | `file_write_read` | file_write/file_read внутри дома | ✅ |
| 5 | `web_search_returns_links` | search_web (ddgs) возвращает результаты | ✅ |
| 6 | `shell_readonly_blocks_dangerous` | readonly профиль блокирует rm -rf | ✅ |
| 7 | `hitl_denied` | autoApprove=false + отказ → тул отменён, запись в audit | ✅ |

## Цели по фазам (из карты)

- **Ф1**: +5 кейсов → 12/12 (компакция сохраняет факт, провайдер-тест, health,
  keyring round-trip, миграция 0.1.0)
- **Ф2–Ф5**: держать 12/12 после каждого регресс-гейта.

## Примечания

- Модель: `deepseek:deepseek-chat` (flash), профиль readonly, изолированный
  ALOTH_HOME — тесты не касаются реальных данных.
- Известный нюанс (из HANDOFF): flash сам не вызывает тул без явной просьбы
  («запомни» без «вызови тул»). В evals промпты явно требуют вызов.
