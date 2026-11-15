# Codex Team — Product Evolution, 14–15 ноября 2026

## Scope, версия, авторизация

Базовый master: `0269b3db6b8d485b6880784f827c9719984aaabb` (RC11). Кандидат **1.0.0-rc12**, ветка `feature/rc12-product-evolution`, [PR18](https://github.com/LosarOS/codex-team/pull/18). Объём одобрен владельцем. Финальный merge/публикация требуют отдельного подтверждения и пока не выполнялись.

Managed Linux executor, Python3.12.14, Node/Chromium; native проверки на одноразовых Windows GitHub runners. Внешний платный API и live AI-миссии не запускались. При старте реального desktop SDK может читать состояние account; эти account calls не измерены и не подменены нулём.

## Реализовано

- Task Architect: сохраняемый план до20 шагов, критерии, файлы, зависимости/DAG, CAS и связь с версией спецификации. Читаемые названия зависимостей. Только явно выбранный корневой актуальный шаг может после подтверждения заполнить существующий composer. Это не автоматический executor зависимого графа. Защита черновика, стандартные права и изоляция сохраняются.
- Project Knowledge: привязка к HEAD/хешу источника, статусы current/stale/review_required/unknown, bounded context512..12000. Старые/повреждённые metadata исключаются из context и сохраняются для ручного review; внешние инструкции обозначены недоверенными данными.
- Mission Control: хронология настоящих событий, дедупликация/фильтрация выбранного запуска, причины блокировки и доступные следующие действия. Нет фиктивных процентов и автоматического повторного запуска.
- Budget: экспорт текущей страницы с фильтрами проекта/UTC-дня, без текстов задач и rawusage. Неизвестные токены/стоимость/квота остаются unknown/null. Browser сохраняет показанный snapshot; desktop заново запрашивает те же фильтры через фиксированный backend URL и открывает native Save. Cancel/error native bridge не переходят в Blob fallback. Поля пути/JSON не принимаются от JavaScript.
- RU/EN README и руководства, оригинальная SVG/PNG-графика, сохранённая лицензия и существующие публичные имена артефактов.
- Security: исправлены подтверждённые исключения malformed usage/sourcebinding; opentelemetry-api1.45.2 и setuptools84.1.0 вместо уязвимых pinned версий.40 runtime desktop pins:0 обнаруженных advisories/0 пропущенных в финальном аудите. Отдельный toolchain pip обновлён26.3; не выдаётся за изменение приложения.

## Тесты

Приложение кандидата соответствует source `6e00643676dd9b2e701fdccf50fa8b75ff59fd00`; последующие изменения — probe/docs/tools, не входные файлы frozen приложения.

- Windows полный suite: **985 passed,1 skipped**,986 total,800.037s, [native build43653777510](https://github.com/LosarOS/codex-team/actions/runs/43653777510). Один opt-in Docker skip, не отключение regression tests. +108 уникальных случаев относительно RC11.
- Финальный локальный полный suite: **982 passed,4 skipped**, Linux Python3.12.14.3 Windows-only +1 Docker; exact cases/source/duration в `evidence/evolution-2026-11-14/local-regression.json`. Не суммируется с Windows или поднаборами.
-15 Node suites passed, `evidence/evolution-2026-11-14/node-contracts.json`.
- Real FastAPI/SQLite +Chromium:7 сценариев passed,0 page errors. Матрица9 тем×2 языка,108 layout checks, keyboard selection;18 настоящих Chromium PNG. Это Linux browser, не доказательство Windows WebView2/DPI.
- Native bridge browser contract5 cases: host mocked, не доказательство системного Save.

## Реальные Windows дистрибутивы

Build43653777510 **SUCCESS**, publish=false. PyInstaller, настоящий x64 EXE, portable extraction/backend/restart, установщик per-user, shortcuts/Unicode, repair/reinstall/uninstall и сохранение profile; новый frozen API smoke проверяет budget/plan/context/no dispatch/restart. Публикация jobSKIPPED.

Независимо скачаны исходные байты, сверены SHA256, размеры, CRC/пути ZIP, x64 app PE и portable marker, отсутствие именованных user-data, идентичность EXE внутри setup ZIP. Подробный результат: `evidence/rc12-candidate/independent-artifact-verification.json` и воспроизводимый `../tools/VERIFY-REVIEW-CANDIDATE.md`.

| Файл | Байты | SHA256 |
|---|---:|---|
| CodexTeam-Portable-x64.zip |249664641|edcd6aa0bfad62e0eb27dc24b2a587d0fcc176f89d46515c24795d9641f498f1|
| CodexTeam-Setup-x64.exe |155690448|4167681ec22e02b327947291fe21cf6f7bdc27d5d51dda0de07eee843ad00add|
| CodexTeam-Setup-x64.zip |155225291|439d403d25401128c218a14c7ff7b696990f8e821bec2084c0e40cb0f61622b3|

Отдельные review artifacts исходного build доступны через [review43657127286](https://github.com/LosarOS/codex-team/actions/runs/43657127286): portable14138946503, installers14138207948, evidence14138841721. Review workflow затем завершился ошибкой GUI probe; binary-byte validation до этой ошибки прошла, но **весь этот run не объявляется SUCCESS**. Артефакты имеют ограниченный срок хранения, это ещё не публичные Releases download URLs.

## Native GUI — активный blocker

Реальный portable EXE показал окно/форму, прочитал owned portable profile и открыл системный Save As. На checkpoint сохранение итогового JSON и graceful Quit **NOT VERIFIED**. Повторное WM_SETTEXT/BM_CLICK не доказало сохранение файла; приложение не объявляется неисправным без доказательств, probe диагностируется по настоящим PNG/UIA/логам.

Экспериментальная ветка `ops/native-gui-experiment` использует тот же неизменный portable с проверенной provenance; ошибки сохраняются, не маскируются. Исходные native GUI runs43653807537,43654680389,43655884118,43656754684,43657127286,43658827916 отражают отдельные проблемы harness/host. Нельзя суммировать частичные успехи в полный PASS. На старом app до native bridge обнаруживалось отсутствие системного Save; контрактный app-gap исправлен и покрыт29 native cases, затем реально подтверждено появление picker, но не запись до настоящего финального успешного прогона.

## Ограничения / следующий шаг

Закончить реальный native Save+штатный Quit, затем включить обязательный gate для финальной Windows-кандидатной сборки, сохранить screenshot/proof и запросить публикацию. Физическая Windows10/11, DPI, Narrator, RDP, длительный soak и успешная live Codex mission **NOT VERIFIED**. Бинарники unsigned; SmartScreen/антивирусная приёмка не заявляются.

Публичный RC11 остаётся download в README до выпуска RC12. Main/tags/releases продуктов не изменены. Метаданные description/topics/homepage/social preview не применены: GitHub integration вернула403. Профильный README LosarOS опубликован отдельно через согласованный scope без смены позиционирования/личных контактов.
