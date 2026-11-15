# Codex Team → SHIFT: настоящий ограниченный эксперимент

Дата: 2026-11-15. Статус: **LIVE MISSION BLOCKED / END-TO-END DEVELOPMENT NOT VERIFIED**.

Это настоящий запуск через текущий Codex Team FastAPI/uvicorn HTTP → Engine → официальный CodexProvider/SDK, без FakeCodexProvider, mock-ответов и замены на прямой `codex exec`. Вызовы выполнены на Linux cloud runtime; Windows-сборки продуктов проверяются отдельно.

## Источники и изоляция

- Код Codex Team: `ccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6`; HEAD при запуске `33a1e5194d1bb59374cf06af5150984e76333365`. Код приложения, зависимости, agents и packs между ними идентичен; разница — документация.
- SHIFT: новый независимый clone exact main `a5effcdcc4861ff099636be7782dd5155a029671`, без изменений реальной рабочей копии.
- Данные эксперимента — новый owned каталог; существующие Codex Team history/settings и исходный SHIFT не использовались на запись.
- Git worktree действительно создан: branch `codex/run_e61a05cb3b9e`, HEAD совпадает с исходной ревизией SHIFT. Исходный clone и worktree после запуска чистые.

## Реальная задача и конфигурация

После чтения существующих `BackupCatalogTests.cs` обнаружен конкретный пробел: проверены Unicode-имя пространства и директория, но нет комбинированной проверки `.db` filename `Учёба 🧪 2026.db` через inventory + inspection с сохранением полного пути, количества записей, исходных байтов и live state.

Агенту поручен один новый файл `tests/Shift.Tests/UnicodeBackupCatalogTests.cs`, предпочтительно до50строк. Только owned temporary SQLite fixture, без изменений production/старых тестов, commit/push/merge, установки пакетов или сети. Ожидаемый результат — настоящий focused .NET10 xUnit regression. **Этот тест не был создан вручную вместо агента.**

Конфигурация:

| Поле | Значение |
| --- | --- |
| Run | `run_e61a05cb3b9e` |
| Backend | `codex_chatgpt` |
| Mode | `implement` |
| Pipeline | coordinator → developer → qa → reviewer |
| Access | standard, isolated=true, auto_commit=false |
| Max calls | 4 |
| Duration | 300секунд |
| Max iterations / parallel agents | 1 / 1 |
| Token guard | 40000 измеренных токенов между этапами; не hard provider cap |
| Reasoning | medium |
| API fallback | отсутствует |

PATH включал установленный .NET10 SDK; зависимости уже прогревались другими проверками. В этой миссии ни исполнение .NET, ни доступ к runtime/cache агентом не были подтверждены: developer не стартовал. Разрешения не расширялись для обхода ограничений.

## Что произошло

1. **До вызова агента** `/api/status` настоящего продукта подтвердил `CONNECTED` и `account.type=chatgpt`. Личные данные ответа не публикуются.
2. `/api/runs` действительно создал запуск. Engine создал независимый worktree и штатный pipeline.
3. Coordinator начал первую SDK agent attempt; созданы thread и turn, получены настоящие события начала/завершения.
4. SDK вернул ошибку обновления авторизации: `Your access token could not be refreshed because you have since logged out or signed in to another account. Please sign in again.`
5. Продукт перешёл в **AUTH_REQUIRED**, создал action_required и остановил исполнение. Автоматического повтора или платного API fallback не было.

CLI login status / SDK account_read могут показывать тип сохранённой учётной записи, но это не доказательство пригодности refresh-сессии для реального turn. Здесь эта разница подтверждена настоящим выполнением.

## Фактические результаты

- Agent attempts: **1**, coordinator. Это счётчик Engine, а не доказательство успешной оплаченной/модельной генерации.
- Принятых agent results: нет. Developer, QA и reviewer: **NOT STARTED**.
- Observed elapsed: **4.71секунды**, включая account-check/setup и наблюдение состояния, до cleanup; это не performance benchmark.
- Наблюдаемые токены и модель: **null / unknown**; usage отсутствует. Нули не подставлены.
- Изменённые файлы: нет. [Настоящий diff](observed.diff) пуст.
- Тесты агента: **NOT RUN**. QA/review diff: **NOT VERIFIED**.
- Оба Git дерева чистые. Engine/uvicorn закрыты, driver завершился с exit0; последующий scoped process scan по owned cwd не обнаружил оставшихся процессов. Данные и worktree оставлены для review; owner profile не удалялся. Backend уже закрыт, поэтому ради фотографии он не перезапускался; runtime-скриншотов этой миссии нет. Никакой код не включён в релизы и не отправлен отдельным SHIFT PR.

[Структурированный отчёт](live-experiment.json) содержит точные state/events/config/source/time. Идентификаторы проекта/запуска — синтетические. Токены, сведения аккаунта, raw SDK logs и private host paths не публикуются.

## Следующее действие

Для продолжения нужен новый официальный вход ChatGPT/Codex в среде запуска с пригодной refresh-сессией. После этого — отдельное явное возобновление/новая ограниченная миссия через Codex Team; текущий результат не даёт права автоматически повторять работу. Платный API, full-access или обход sandbox не использовались и не предлагаются как скрытая замена.
