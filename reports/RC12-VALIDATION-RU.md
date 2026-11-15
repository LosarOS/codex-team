# Codex Team RC12 — итог кандидата, 15 ноября 2026

## Результат и источники

Кандидат **1.0.0-rc12** реализован и собран от объединённого master. Автоматические release gates: **PASS**. Публичный release status: **BLOCKED — ожидается отдельное подтверждение владельца на публикацию**. Live SDK development: **PARTIAL / AUTH_REQUIRED**, успешная end-to-end миссия не подтверждена. Stable1.0 не назначена.

База: master `0269b3db6b8d485b6880784f827c9719984aaabb`, публичный RC11. Проверенный binary source: **`ccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6`**. [PR18 merged](https://github.com/LosarOS/codex-team/pull/18) · [Windows43665690346](https://github.com/LosarOS/codex-team/actions/runs/43665690346) · [read-only byte/proof review43667875815](https://github.com/LosarOS/codex-team/actions/runs/43667875815). Оба runs SUCCESS; публикационные jobs не выполнялись. Master фактически protected=false; обычное слияние входило в согласованный scope, настройки защиты не менялись. Последующие docs-only commits не меняют приложение.

## Возможности

| Изменение | Статус и граница |
|---|---|
| Редактируемый Task Architect plan | VERIFIED: версии/CAS, циклы/зависимости/shared-files; настоящий browser save/reload/ошибка и ручной root-step handoff |
| Свежесть Project Knowledge | VERIFIED: HEAD/hash, current/stale/review_required/unknown, malformed metadata; real source-change/context preview |
| Mission Control timeline/blockers | VERIFIED в backend/Node/browser contracts; actual AUTH_REQUIRED stop наблюдался в SDK-эксперименте |
| Budget export | VERIFIED: выбранная страница/фильтры, unknown values, real backend + browser download и native Save/записанный JSON |
| Startup readiness | VERIFIED: neutral checking, отдельный health, stale response guard, unknown auth gating, реальный Windows UI indicator |
| Полная agent-разработка SHIFT через SDK | BLOCKED: refresh-сессия недействительна, developer/QA/reviewer не стартовали |

План до20шагов не исполняется автоматически. Только явно выбранный актуальный независимый root step после подтверждения переносится в существующий composer со standard access, isolation и auto_commit=false. Далее нужен отдельный Start. Новая память остаётся локальными недоверенными данными; stale/unknown записи сохраняются для review и исключаются из bounded context512..12000.

Timeline использует реальные события, сортировку/дедупликацию и выбранный run. Budget export включает текущую страницу с project/UTC-day filters, без task text/private paths/raw provider payloads. Unknown cost/quota/tokens не превращаются в0. Browser сохраняет показанный snapshot; desktop заново получает те же фильтры через фиксированный backend URL. Native cancel/error не вызывает скрытый Blob fallback.

## Исправления

- Malformed source bindings/usage projections больше не приводят к подтверждённым исключениям; добавлены regression cases.
- Desktop export действительно использует native Save; контролируемый bridge принимает только фильтры, не JS-путь/JSON для произвольной записи.
- При startup раньше online=false показывал ложный красный offline до первого ответа; SDK account latency также ошибочно определяла transport. Теперь /health независим, unknown SDK не равен auth-required, execution guards требуют свежий известный provider result. Неизменившийся aria-live subtree сохраняется при polling.
- Уязвимые opentelemetry-api/setuptools pins обновлены. [Точный audit40pins/0findings/0skips и исключения](DEPENDENCY-AUDIT-2026-11-14.md).

## Тесты

| Среда | Passed | Skipped | Failed/errors | Всего |
|---|---:|---:|---:|---:|
| Windows полный source suite exact master T |1041|1|0|1042|
| Linux Python3.12.14 |1038|4|0|1042|

Windows duration1043.844s — время pytest, не benchmark приложения. Linux74.63s. Один opt-in Docker skip; три дополнительные Linux-skips относятся к Windows subprocess/junction cases. Docker не нужен для обычной установки/сборки. Наборы между средами, targeted и повторные runs не суммируются.

Root отдельно выполнил16Node suites. Real FastAPI/SQLite/Chromium:8workflow checks,9тем×2языка,108layout checks на двух ширинах, keyboard selection,0page errors. Синтетический Git-проект/guard исключили реальные model calls; это browser/component evidence. Source IDs и raw results: [startup regression](evidence/rc12-startup-regression/README.md). Изолированные test paths и текущий production input эквивалентны master T; полный Windows suite выполнен непосредственно от T.

Один dev-tool warning Starlette/httpx TestClient сохранён; тесты не фильтровались ради зелёного результата. Он не выдаётся за runtime дефект.

## Реальный Windows runtime

На одноразовом Windows Server2025 x64 выполнены frozen build, extracted portable/backend/restart, per-user installation, Unicode shortcuts, same-version repair, uninstall/reinstall, history/settings/queue/drafts/templates/notebook preservation. Ни одна миссия не стартовала автоматически после restart. Updater check выполнен; полный исторический RC11→RC12 update через пользовательский UI не заявляется.

Настоящий EXE/WebView2 показал форму, актуальный UI backend indicator, portable profile, системный Save, записал валидный JSON и завершился native exit0. После закрытия owned GUI/backend процессов0, force cleanup не использовалась. Наблюдаемый label «Нужен вход» соответствует пустому изолированному Codex profile и рабочему backend. SDK startup account-call count **unknown/null**. Первый ложный offline сохранён как historical before-frame; новая исходная картинка его не ретуширует.

[Оригинальные proofs и независимо проверенные actual bytes](evidence/rc12-main-candidate/README.md) · [Настоящие Windows screenshots](../docs/screenshots/rc12-main-candidate/README.md) · [Сравнение startup до/после](RC12-STARTUP-READINESS-FIX.md). GUI gate проверяет ограниченный набор сценариев; сохранённый JSON body не включён в allowlisted публичный GUI archive. Общая интерактивная приёмка не объявляется завершённой.

## Cross-project: Codex Team → SHIFT

Настоящий HTTP→Engine→official SDK запуск `run_e61a05cb3b9e` использовал новый clone SHIFT maina5effcd, Implement, standard/isolated/no auto-commit,4calls/300s и measured-token guard40000 (не hard provider cap). Account metadata сообщала ChatGPT; первая coordinator attempt получила реальную ошибку refresh-сессии и **AUTH_REQUIRED**. Созданы worktree/thread/turn, accepted results нет. Developer/QA/reviewer NOT STARTED, изменений и agent tests нет. Calls1attempt, модель/токены unknown/null, наблюдаемое время4.71s. Автоповтора, paid API fallback и обхода sandbox не было.

Root независимо прочитал persisted SQLite, проверил real default provider/no Fake в driver, caps4/300 и чистоту clone/worktree. Runtime закрыт, scoped owned-process check не нашёл оставшихся процессов. [Подробные events/config/source/diff и границы](crossproject-2026-11-15/README.md). Для успешной миссии нужен новый официальный вход и отдельный явный запуск; прошлый результат не даёт права автоматически повторять работу.

## Файлы для review

[Portable artifact](https://github.com/LosarOS/codex-team/actions/runs/43667875815/artifacts/14143076340) · [Installer artifacts](https://github.com/LosarOS/codex-team/actions/runs/43667875815/artifacts/14142851753) · [SHA256 и original evidence](https://github.com/LosarOS/codex-team/actions/runs/43667875815/artifacts/14142457332).

| Файл | Байты | SHA256 |
|---|---:|---|
| CodexTeam-Portable-x64.zip |249666849|ad05e0966417e3173f5dda3847c0d6ddf98b10474459e063d833e3531eb9be65|
| CodexTeam-Setup-x64.exe |155694288|7d1f9a3d66212037447e2cbf85b0df89deeafc566defac431ab62fb7726e2003|
| CodexTeam-Setup-x64.zip |155228614|5968713c05b6458f24b88ea8ccd5206bd6480bc2b049a3b407785d9e2be983bd|

Это временные Actions artifacts; требуется GitHub-доступ. Публичные downloads пока RC11. Скачанные raw files сверены по SHA256/размеру, ZIP CRC/paths/duplicates, x64 application PE, portable marker и named-user-data guards. Installer stub x86 допустим для Inno, payload приложения x64; EXE внутри setup ZIP идентичен standalone. Оба PE unsigned, нет сертификата; SmartScreen/антивирусная сертификация не проводилась. Proof provenance не является подписанной attestation.

## Данные, UX и GitHub

Существующие SQLite/history/projects/agents/packs/worktrees/drafts/templates/queue сохранены. Новые планы/knowledge metadata используют существующий SuiteStore, destructive DDL миграций нет. Старые и повреждённые knowledge metadata сохраняются для ручного review. Permission profiles, frozen budgets, explicit start, safety stops и отсутствие автоматического merge продукта остаются.

RU основной README, полный EN, руководства/release notes, реальные browser/native images и оригинальные SVG/PNG включены. Профиль LosarOS обновлён отдельным PR1. Description/topics/homepage/social-preview settings остались PARTIAL: API403, browser tools недоступны. Публичные контакты/лицензия/права доступа/публичность не менялись.

## Оставшиеся ограничения и следующий шаг

- Физические Windows10/11, DPI100/125/150/200%, Narrator/high contrast, RDP, mixed monitors, sleep и длительный soak NOT VERIFIED.
- Успешная live SDK development mission BLOCKED_AUTH; не считать подписочный account metadata доказательством действующего refresh.
- Same-version repair и unit compatibility fixtures не доказывают каждый исторический installer upgrade.
- Контролируемый app performance benchmark NOT MEASURED; чисел ускорения/потребления квоты не придумано.
- Следующие функциональные проекты: зависимые миссии/параллельные writers и безопасная интеграция worktrees требуют отдельной архитектуры. Текущая очередь остаётся независимой.

После отдельного одобрения — публикация prerelease предусмотренным workflow с полными gates, проверка final source/tag и повторное скачивание опубликованных бинарников/контрольных сумм. Полная stable-приёмка остаётся отдельной задачей.
