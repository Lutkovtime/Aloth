# Сборка установщика Aloth (Windows)

## 1. Собрать PyInstaller onedir (CLI + GUI)

Из корня проекта `C:\Hermes\Aloth` (нужен dev-dep pyinstaller: `uv add --dev pyinstaller`):

```bash
uv run pyinstaller --noconfirm --name aloth --onedir --collect-submodules aloth \
  --exclude-module logfire --copy-metadata genai_prices --copy-metadata pydantic_ai_slim \
  --copy-metadata mcp --icon assets/logo.ico --distpath dist --workpath build scripts/launcher_cli.py

uv run pyinstaller --noconfirm --name aloth-gui --onedir --windowed --collect-submodules aloth \
  --exclude-module logfire --copy-metadata genai_prices --copy-metadata pydantic_ai_slim \
  --copy-metadata mcp --icon assets/logo.ico --distpath dist --workpath build scripts/launcher_gui.py
```

Флаги обязательны:
- `--exclude-module logfire` — плагин logfire делает `inspect.getsource` → OSError в frozen-приложении.
- `--copy-metadata genai_prices pydantic_ai_slim mcp` — без них `importlib.metadata` падает
  `PackageNotFoundError` при старте.

## 2. Установить Inno Setup 6

Скачать: https://jrsoftware.org/download.php/is.exe

Тихая установка (из bash/MSYS, из каталога с is.exe):

```bash
./is.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /SP-
```

После установки компилятор: `C:\Program Files (x86)\Inno Setup 6\iscc.exe`

## 2. Собрать installer

Из корня проекта `C:\Hermes\Aloth`:

```bash
"C:/Program Files (x86)/Inno Setup 6/iscc.exe" installer.iss
```

Результат: `dist/Aloth-Setup-0.1.0.exe` (установка без прав администратора, в `%LocalAppData%\Programs\Aloth`).
