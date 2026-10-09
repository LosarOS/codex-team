# Установка Codex Team 1.0.0-rc1

Поддерживаемая целевая платформа — Windows 10 x64 build 19041+ / Windows 11 x64. Нужны Git, WebView2, Windows .NET Framework для GUI и интернет для выбранного provider. Bundle включает Python/Codex; project dependencies устанавливаются отдельно.

Запустите `installer/CodexTeam-Setup-x64.exe`, затем Desktop/Start Menu shortcut. Installer per-user, default `%LOCALAPPDATA%\Programs\CodexTeam`; администратор для приложения не требуется. Если WebView2 отсутствует, interactive setup предлагает Microsoft-signed bootstrapper; silent setup требует готового WebView2. Git installer не устанавливает и не меняет.

```powershell
.\installer\CodexTeam-Setup-x64.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /TASKS=desktopicon
& "$env:LOCALAPPDATA\Programs\CodexTeam\unins000.exe" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
```

Portable ZIP распакуйте целиком в writable directory; `portable.json` выбирает `data/` рядом с EXE. Installed state — `%LOCALAPPDATA%\CodexTeam`. Явный `CODEX_TEAM_DATA_ROOT` переопределяет оба варианта. Запуск только EXE без `_internal` не поддерживается.

Выберите clean Git root и завершите официальный ChatGPT/Device Code login. API key не нужен default provider. Для OpenAI API отдельно подтвердите billing и сохраните собственный ключ. [Providers](docs/PROVIDERS.md).

Обновление ручное: завершите/поставьте на паузу задачу, полностью Quit, запустите новый setup. Uninstall сохраняет user state, projects и Codex auth. Перед schema-changing update сделайте backup закрытого data root. Fresh-install и final polished acceptance подтверждаются только фактическими release reports.
