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

## Native GUI checkpoint — 15 ноября, 00:42UTC

[Эксперимент43659404286](https://github.com/LosarOS/codex-team/actions/runs/43659404286) **SUCCESS**. Исходный frozen кандидат6e00643, probe8c551c0. Root независимо прочитал `evidence/rc12-native-gui/native-gui-proof.json`, сохранённый JSON и просмотрел PNG с фактическим системным Save/предпросмотром. Шесть наблюдаемых gates true, native exit0, оставшихся процессов0, force cleanupfalse. SDK account callsnull; physicalWindows/DPI false.

Причина предыдущего probe-сбоя: WM_SETTEXT/BM_CLICK не доказали ввод/сохранение modern dialog. Успешный probe использует проверенный foreground owned dialog, точный Edit HWND/focus, один keyboard ввод с readback и одно действие Save. Проверки файла/схемы/штатного выхода не убирались.

Это обновляет предыдущий checkpoint **только для этих наблюдаемых сценариев**, а не всего GUI matrix. Настоящие PNG, неизменённые байты/хеши и provenance: `../docs/screenshots/rc12-native-gui/README.md`. Финальная canonical Windows-сборка получает обязательный GUI gate; её результаты будут записаны отдельно.

## C0 checkpoint и финальный startup review

Canonical [43659810614](https://github.com/LosarOS/codex-team/actions/runs/43659810614) **SUCCESS**, sourcec0e6f8f:1025 passed/1 skipped/1026total,984.022s Windows. Final Linux1022/4. [Read-only review43661926960](https://github.com/LosarOS/codex-team/actions/runs/43661926960) такжеSUCCESS: скачанные original binaries/proofs сверены, три split archives повторно скачаны root через GitHub connector и проверены независимо. Все оригинальные evidence сохранены в `evidence/rc12-final-candidate/`; эта папка идентифицирует **C0 checkpoint**, не будущий startup-fix binary.

При реальном просмотре первого Windows PNG обнаружен ранний красный badge «Сервер недоступен». Код подтверждает initial online=false +render до первого запроса; отдельное смешение transport/SDK: /api/status включает медленный account discovery, HTTP timeout12s при SDK bound20s. После этого Budget/native Save/quit работают, поэтому постоянная недоступность не доказана. Важный UX-дефект выбран для исправления перед окончательной публикацией.

Planning agent реализует neutral initial checking, отдельный cheap /health/latest-probe-wins и явные pending/unverified состояния SDK без ложного auth-required; доступы/permissions/start guards сохраняются. Control agent добавил mandatory native UIA backend_connection_verified/observedlabel перед первым screenshot:144a6ae. При этом app-fix ещё проходит targeted/Node review; новые binary/core counts должны быть подтверждены следующей canonical Windows-сборкой. Старые C0 hashes и1025 tests нельзя выдать за доказательство нового app source.

Root готовит повторный real-backend Chromium прогон в новом каталоге, без перезаписи исторических PNG. Оплачиваемые model/API calls не выполняются. SDK discovery calls GUI остаются null. Публикация/merge всё ещё ожидают отдельного подтверждения после конкретного review.

## Startup-fix checkpoint — application68d0ad8 / candidate6807cac

App fix68d0ad8 и обязательный UIA backend-readiness gate144a6ae интегрированы. Root самостоятельно выполнил полный Linux suite: **1038 passed/4 skipped/0 failed**,74.63s; все16Node contracts с корректным static-directory аргументом passed. Real FastAPI/SQLite/Chromium:8 workflow checks,18theme×language combinations/108layout checks,0page errors. Сырые источники/результаты: `evidence/rc12-startup-regression/` и `../reports/rc12/startup-fixed-browser/`. Fixture запретил real SDK connection и не создал run.

[Новая canonical Windows43663714379](https://github.com/LosarOS/codex-team/actions/runs/43663714379), exactsource `6807cacc204aca982614ad68fab50db5e0dcef2e`, fullsource=true/publish=false: **IN PROGRESS**. Предыдущий C0 остаётся проверенным промежуточным кандидатом и не доказывает этот frontend fix. Нативный gate теперь ждёт настоящий видимый healthy transport label, записывает его и только затем делает первый screenshot. Start/Resume/login остаются ограниченными до свежего известного provider result. Нет новых model calls или изменения разрешений.

## Финальный master source и реальный SDK auth stop

API проверка master.protected=false позволила обычный согласованный merge PR18 без дополнительного запроса: **masterccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6**. Публичные Releases не публиковались и ожидают отдельного подтверждения. Canonical43665690346 и read-only review43667875815 **SUCCESS**. Actual source tests1041/1/1042,0fail/errors. Root скачал finalmain rawportable/installer archives, независимо сверилSHA/ZIP/PE/source proofs и просмотрелactualfirstframe: рабочий backend и корректныйknownAuthRequired для emptyownedCodexprofile. Details: [итоговая валидация](RC12-VALIDATION-RU.md).

Отдельно выполнен реальный HTTP→Engine→official SDK эксперимент на новом cloneSHIFT. Он остановлен AUTH_REQUIRED после1попытки/4.71s, безfallback/retry; принятых результатов нет, tokens/modelnull. Root readonlySQLite/driver/Git подтвердилactualstate, caps4/300 и чистые деревья. [Exact report](crossproject-2026-11-15/README.md). Это частичная проверка механизма остановки, не успешная разработка. Данные и worktree оставлены вownedexperimentfolders; существующиеownerprofiles/релизныйкод не менялись.

Docs-only follow-up docs/rc12-final-validation содержит originalmain proofs/screenshots, финальные guides/release notes/report иsanitizedexperiment. Он не меняет production/тесты/dependencies/workflows. Послеmerge отдельно требуется одобрение публичных prereleases, finaltag/source verification и повторное скачивание публичныхassets/SHA256.


## Publication checkpoint — 2026-11-15

Owner explicitly approved publication. **Codex Team1.0.0-rc12 is public**, source/tag `2611575e3b814f0ebcf4289f547fe2f196ee8411`, [Windows run43695702130](https://github.com/LosarOS/codex-team/actions/runs/43695702130) SUCCESS including build and publish. Full Windows suite1041passed/1opt-inDocker skip/0failures; native portable/installer/preservation/WebView2/backend indicator/Save/graceful-exit gates passed. Root independently downloaded ALL13 public assets and checked bytes/GitHub digests/checksum manifest/ZIP CRC; embedded installer matches standalone EXE. [Publication report](RELEASE-PUBLICATION-2026-11-15.md). Earlier candidate proofs keep their original sources. This checkpoint supersedes historical pending-publication text above. **VERIFIED PRERELEASE WITH DISCLOSED LIMITATIONS**, unsigned; full physical Windows acceptance and successful live SDK development remain unverified. No reauthentication/retry or paid API fallback was initiated by publication.
