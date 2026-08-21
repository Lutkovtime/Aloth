# Aloth — Spike Report (Фаза 0, 21.08.2026)

> Де-риск четырёх технических вопросов до начала фич. Каждый вердикт —
> письменный, с воспроизводимым тестом.

---

## 1. Nuitka standalone + PySide6 + qt-material + QtAwesome

**Вердикт: РАБОТАЕТ — Nuitka остаётся основной сборкой.**

- Команда: `uv run nuitka --standalone --enable-plugin=pyside6 --output-dir=dist_spike spike/nuitka_spike.py`
- Среда: Windows 11, Python 3.11 (uv), Nuitka 4.1.3. Компилятор — MinGW gcc
  15.2.0 (Nuitka скачал сам, Windows SDK в VS не понадобился → CI не требует
  Visual Studio).
- Сборка: ~5 мин (ccache). Все data-files qt-material (fonts/resources/themes,
  18+39+26 файлов) и qtawesome (fonts) включены автоматически.
- Проверка (offscreen, на собранном `nuitka_spike.exe`): иконка QtAwesome
  загружается, QSS qt-material применён (styleSheet len=30728), окно создаётся,
  high-DPI dpr=1.0, палитра из темы доходит. **6/6 PASS.**

Вывод: развилка из плана (Nuitka vs PyInstaller) решена в пользу Nuitka.
PyInstaller остаётся fallback'ом в docs/build.md, но не основным путём.

## 2. keyring / Windows Credential Manager в frozen-сборке

**Вердикт: РАБОТАЕТ.**

- Dev: бэкенд `keyring.backends.Windows.WinVaultKeyring` (настоящий Credential
  Manager, не заглушка), round-trip set/get/delete — PASS.
- Frozen (Nuitka standalone `keyring_spike.exe`): тот же WinVaultKeyring,
  запись/чтение/удаление секрета — **PASS**.
- Nuitka сам подтянул keyring + его бэкенды без спец-плагина.

Вывод: `secrets.py` (Фаза 1.3) может смело использовать `keyring` —
фrozen-сборка не теряет доступ к Credential Manager.

## 3. WinSparkle (автообновление)

**Вердикт: РАБОТАЕТ через ctypes — pywinsparkle мёртв.**

- **pywinsparkle (обёртка) — не пригоден:** последний релиз 1.6.0 (2017),
  колёса только до Python 3.6 (cp36), sdist отсутствует, репозиторий удалён.
  Установка на Python 3.11 невозможна.
- **WinSparkle (сама библиотека) — живая:** v0.9.4 (июль 2026),
  `WinSparkle.dll` x64 + `winsparkle-tool.exe` (генерация EdDSA-ключей,
  подпись appcast, проверка).
- Спайк (`spike/winsparkle_spike.py`, ctypes): keygen → appcast.xml →
  sign (EdDSA) → verify «Valid signature» → DLL грузится, все 8 API-функций
  резолвятся, `init`+`cleanup` проходят. **16/16 PASS.**

Решение: в Фазе 4 пишем тонкий `src/aloth/updater.py` на ctypes поверх
WinSparkle.dll (поставляем DLL в сборку), appcast.xml подписываем EdDSA
через winsparkle-tool. Никаких pip-зависимостей.

## 4. PoC компакции (PydanticAI agent.iter())

**Вердикт: РАБОТАЕТ — API даёт всё нужное для context.py.**

- `Agent.iter()` — asynccontextmanager, внутри `async for node in run`
  (узлы UserPromptNode / ModelRequestNode / CallToolsNode / End).
- `run.all_messages()` — полный snapshot истории; передаётся в новый
  `agent.iter(message_history=...)` для продолжения.
- Компакция (суммаризация + protect_last_n): сжимаем историю между ранами
  (summary как SystemPromptPart «CONTEXT CHECKPOINT» + последние N сообщений),
  новый раунд стартует со сжатой историей, ответ модели приходит, summary
  сохраняется в финальной истории. **5/5 PASS** (диалог 4 хода, сжатие 4→3).
- Модификация `ctx.state.message_history` mid-run также возможна (mutable),
  но для context.py достаточно передачи `message_history` между ранами.

Вывод: `context.py` (Фаза 1.1) строится на `agent.iter()` + `message_history`,
без форка PydanticAI.

---

## Принятые решения (влияют на Фазу 4)

1. **Сборка:** Nuitka standalone (основная). PyInstaller onedir — fallback.
2. **Обновления:** ctypes-обёртка над WinSparkle.dll v0.9.4 + EdDSA appcast.
   pywinsparkle не используется.
3. **Секреты:** keyring (WinVaultKeyring) работает и в frozen.
4. **Компакция:** через `agent.iter()`/`message_history`, модуль `context.py`.

## Артефакты спайка

- `spike/nuitka_spike.py`, `spike/keyring_spike.py`, `spike/winsparkle_spike.py`,
  `spike/compaction_poc.py` — воспроизводимые тесты (не входят в пакет).
- `spike/winsparkle/` — распакованный WinSparkle 0.9.4 (DLL + тул, лицензия MIT).
- Собранные exe — `dist_spike/` (мусор, удаляется).
