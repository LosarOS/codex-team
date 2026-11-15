# Codex Team 1.0.0-rc12 — публикация и независимая проверка

**Release status: VERIFIED PRERELEASE WITH DISCLOSED LIMITATIONS.**

Владелец явно подтвердил публикацию. Выпуск опубликован как unsigned prerelease, не stable1.0.

- [Публичный релиз](https://github.com/LosarOS/codex-team/releases/tag/v1.0.0-rc12); `draft=false`, `prerelease=true`.
- Публикация: `2026-11-15T09:00:23Z`. Независимая повторная загрузка закончена `2026-11-15T09:01:23.202280+00:00`.
- Source commit и проверенная цель тега `v1.0.0-rc12`: **`2611575e3b814f0ebcf4289f547fe2f196ee8411`**.
- [Windows workflow](https://github.com/LosarOS/codex-team/actions/runs/43695702130). Полные source tests не пропускались.
- Все приложенные assets повторно скачаны **после** публичной публикации. Для каждого сверены ненулевой размер и GitHub asset digest; для бинарников — опубликованный SHA256SUMS. ZIP проверены по CRC и безопасным именам записей; установщики имеют PE/MZ header. Это проверка целостности, не антивирусная сертификация.
- [Машинный результат](evidence/published-2026-11-15/independent-published-verification.json) · [метаданные Releases](evidence/published-2026-11-15/release-metadata.json) · [SHA256SUMS](evidence/published-2026-11-15/SHA256SUMS.txt).

## Скачивание и SHA256

| Файл | Байт | SHA256 |
|---|---:|---|
| [CodexTeam-Setup-x64.exe](https://github.com/LosarOS/codex-team/releases/download/v1.0.0-rc12/CodexTeam-Setup-x64.exe) | 155706244 | `7253c9b58d63005249c80a56e27d8629b99af89a1c24f6b5207145e0e60c4eef` |
| [CodexTeam-Setup-x64.zip](https://github.com/LosarOS/codex-team/releases/download/v1.0.0-rc12/CodexTeam-Setup-x64.zip) | 155241132 | `af258ff6d1374fc6d779a5178b90f1626faf34f28f499f0d24d3698c9b053716` |
| [CodexTeam-Portable-x64.zip](https://github.com/LosarOS/codex-team/releases/download/v1.0.0-rc12/CodexTeam-Portable-x64.zip) | 249663686 | `0bd2bd81814aaba88a3f1c7b75bca6af83d8c4c7159372acff272788d53a980c` |

Хеши относятся к свежей опубликованной пересборке; хеши предыдущих кандидатов сохранены в прежних отчётах и не выдаются за эти файлы.

## Реальные Windows gates

**1041 passed / 1 skipped / 0 failed / 0 errors**, всего 1042. Source `2611575e3b814f0ebcf4289f547fe2f196ee8411`. Время pytest `659.769` секунд — время набора, не benchmark приложения. Один skip — opt-in Docker; отдельный Docker-модуль QA не обязателен для установки. [Исходный test report](evidence/published-2026-11-15/source-test-results.json).

Извлечённый portable EXE/backend, restart и сохранение профиля; per-user installer, repair/uninstall/reinstall, установленный backend/assets и preservation прошли. Frozen backend проверил сохранение планов, bounded context, экспорт бюджета и отсутствие dispatch. [Portable proof](evidence/published-2026-11-15/portable-smoke.json) · [Installed proof](evidence/published-2026-11-15/installed-smoke.json).

Настоящие WebView2 window/task form, portable marker, реальный индикатор доступного backend, системный Save, запись JSON и graceful exit проверены на disposable Windows Server runner. Source и probe совпадают с публикационным commit. Force cleanup не потребовался, owned GUI/backend processes remaining=0. [Native GUI proof](evidence/published-2026-11-15/native-gui-proof.json). Полная физическая GUI/DPI-приёмка этим не заменяется.

В pytest осталось одно `StarletteDeprecationWarning`: будущая миграция testclient с httpx на httpx2. Оно не скрыто и не является падением тестов. Actions также сообщает о pinned actions на Node20, исполняемых runner через Node24; оба jobs успешны. Обновление action pins требует отдельной проверки.

Установочный ZIP дополнительно проверен: вложенный EXE побайтно соответствует отдельно опубликованному установщику по SHA256. Прикреплённый RELEASE-NOTES-RU.md сохраняет описание предварительных проверок source ccd0500; свежие результаты публикационной пересборки source2611575 приведены выше.

## Пользовательский результат

- Task Architect: редактируемые CAS/versioned планы, зависимости, criteria и явная передача сохранённого root step в composer; нет автоисполнения или автоматического merge.
- Project Knowledge: freshness по исходным файлам, понятные stale/review-required состояния и ограниченный контекст из локальных недоверенных данных.
- Mission Control: реальные события и объяснимые блокировки; frozen budgets, explicit start, isolation и безопасный restart сохранены.
- Budget Guardian: честный page/filter export, неизвестные значения остаются null; desktop использует native Save без скрытого browser fallback.
- Исправлен ложный offline при startup: backend health отделён от проверки SDK; неизвестная авторизация блокирует запуск агентов.
- Исправлены malformed metadata/usage cases и обновлены две dependency pins по подтверждённым advisories; [audit40pins](DEPENDENCY-AUDIT-2026-11-14.md).

## Ограничения и live SDK

Успешная end-to-end разработка SHIFT через живой Codex SDK **NOT VERIFIED**: одна предыдущая изолированная миссия остановлена AUTH_REQUIRED из-за недействительной refresh-сессии до developer/QA/review. Публикация не запускала её повторно и не переключала на платный API. Native GUI SDK account-discovery calls неизвестны (`null`), не0; login/model execution не запрашивались. [Эксперимент](crossproject-2026-11-15/README.md).

Физические Windows10/11/DPI/Narrator/RDP, полная пользовательская приёмка и performance benchmarks остаются **NOT VERIFIED / NOT MEASURED**. Бинарники unsigned; предупреждения SmartScreen не сертифицированы. Снимки в основной gallery показывают ранее проверенный canonical candidate с его оригинальным commit, а не притворяются новой пересборкой.
