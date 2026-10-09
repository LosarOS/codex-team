# Codex Team — локальная команда разработки

Codex Team **1.0.0-rc1** помогает пройти задачу от плана до кода, тестов и review в отдельном Windows-окне. Coordinator, Analyst, Developer, QA и Reviewer имеют собственные Codex threads; история, checkpoints, тестовые команды и Git diff доступны в приложении. Это независимый продукт, использующий официальный Codex SDK.

> **Development RC — приёмка не завершена.** Проверки: 398 passed, 3 skipped; после исправления startup отдельно 30 desktop-service tests passed. Runtime-кандидат прошёл Standard/Resume E2E. В финальном установленном пакете прежний E2E-run не найден в текущем профиле: выбор data root требует проверки. Новые installed Standard/Action Center/portable/scaling проверки ещё не завершены. Перед обновлением сохраняйте оба профиля данных. Подробности: [итоговый отчёт](reports/final-release-validation.md).

Этот репозиторий публикует исходники. Installer и portable ZIP пока доступны локально у автора сборки; для самостоятельной сборки используйте раздел «Разработка». Лицензия приложения пока не выбрана; публичный доступ к исходникам не означает предоставление MIT или другой open-source лицензии.

## Установка

1. Запустите `installer/CodexTeam-Setup-x64.exe`. Installer устанавливает приложение для текущего пользователя и создаёт ярлыки Desktop/Start Menu.
2. Откройте **Codex Team**, при необходимости войдите через **ChatGPT** или **Device Code**.
3. Выберите корень чистого Git-проекта, опишите задачу, выберите режим и нажмите START. Для isolated mode нужен первоначальный commit.
4. После завершения изучите QA/Reviewer и diff. Изменения остаются в отдельном worktree; автоматического merge/push нет.

Целевая платформа: Windows 10 x64 build 19041+ и Windows 11 x64. Нужны Git и WebView2. Python и Codex runtime включены; project Node/.NET SDK/JDK/Rust устанавливаются отдельно. [Подробности установки](INSTALL_WINDOWS.md).

Portable: распакуйте **весь** `dist/CodexTeam-Portable-x64.zip` и откройте `CodexTeam/CodexTeam.exe`. ZIP-only `portable.json` выбирает соседний `data/`, отдельно от installed-данных. Не переносите EXE без `_internal`.

## Возможности

Quick выполняет Coordinator → Developer → QA. Standard добавляет Analyst/Reviewer; Deep — read-only specialists/Final Audit; Audit работает без coding; Plan создаёт план; Implement выполняет существующий замысел. QA/review failures возвращаются Developer до заданного лимита. Specialists последовательные; один Developer остаётся writer.

Pause применяется на границе этапа; Stop отменяет работу. Steer направляет текущую роль, Queue — следующую. Resume из History сохраняет уже завершённые stages; незавершённый stage может повториться. Изменение worktree/checkpoint требует решения пользователя.

Tray открывает окно/текущий run/логи, Pause и Quit. Закрытие активной задачи предлагает **Keep running in tray**, **Stop run and exit**, **Cancel**. Notifications и minimize-to-tray настраиваются. Recovery banner сообщает об abnormal exit; Export diagnostics создаёт ограниченный redacted ZIP через native Save dialog.

## Providers и безопасность

Default **Codex / ChatGPT** использует официальный login и Codex usage, без API key. Optional **OpenAI API** требует собственного ключа в Windows Credential Manager и явного подтверждения separate billing. Ошибка одного provider никогда не включает другой автоматически. API execution проверен mocks; реальные API inference при acceptance не выполнялись. [Providers](docs/PROVIDERS.md).

Clean Git root обязателен; isolated worktree сохраняет исходный checkout. Developer — workspace-write, review-роли — read-only. Action Center показывает разрешения и необходимые решения. Native Codex profile ограничивает tools; local command policy не перехватывает все native commands. [Разрешения](docs/PERMISSIONS.md), [ограничения](LIMITATIONS.md), [агенты/packs](docs/AGENT_PACKS.md).

Installed state находится в `%LOCALAPPDATA%\CodexTeam`, программа — `%LOCALAPPDATA%\Programs\CodexTeam`. Uninstall сохраняет данные, проекты и официальный login. Updater отсутствует: полностью закройте приложение и установите новую версию. [User guide](docs/USER_GUIDE.md), [troubleshooting](TROUBLESHOOTING.md).

## Разработка и release evidence

```powershell
.\setup.ps1
.\run.ps1
.\.venv\Scripts\ai-team.exe status
.\.venv\Scripts\python.exe -m pytest -q
.\build-desktop.ps1
```

`run.ps1` — browser debug UI; CLI execution требует закрытого backend с тем же data root. Сборка создаёт installer/portable, payload report и SHA-256. Application artifacts пока unsigned. Build procedure воспроизводима, побитная идентичность EXE не заявляется.

Подтверждённые baseline/source проверки и final artifact gates раздельно описаны в [RELEASE_NOTES_V1](RELEASE_NOTES_V1.md) и [release checklist](docs/RELEASE_CHECKLIST.md). Старый `docs/FINAL_REPORT.md` относится к MVP, а не финальному RC acceptance.
