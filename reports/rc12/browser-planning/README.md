# RC12 — настоящая browser-проверка на реальном backend

2026-11-14. Linux headless Chromium 1440×1050; реальный FastAPI/SQLite и выделенный синтетический Git-проект. **Это не Windows WebView2 и не живой Codex SDK.** Авторизация возвращает AUTH_REQUIRED; попытка подключения к SDK запрещена assertion-guard. Скриншоты не изменялись.

Выполнены семь проверяемых сценариев: UI создание/сохранение DAG и предупреждение об общих файлах; отклонение цикла без изменения сохранённого плана; bounded context preview с актуальной записью; изменение реального исходника → stale и исключение записи; фактическое скачивание JSON budget export; подтверждаемая подготовка независимого шага с standard/isolated/no-autocommit и отказом зависимому; отсутствие созданных запусков. `results.json` фиксирует итог passed и отсутствие browser pageerrors.

Воспроизведение с Python-зависимостями и Playwright/Chromium:

1. `PYTHONPATH=. python tests/rc12_browser_server.py` (выделенный порт8768, temporary directory).
2. `node tests/rc12_real_backend_browser.cjs http://127.0.0.1:8768`.
3. Остановить fixture-server Ctrl+C. Повторный полный сценарий начинать с новой fixture, а не загрязнённой предыдущими запусками БД.

Файл `RC12_BROWSER_MANIFEST` переопределяет расположение локального указателя fixture-root. Не указывайте реальные пользовательские данные. Скрипт меняет только созданный fixture `main.py`.

Первоначальные ошибки самой проверки: неоднозначный text locator на пользовательской ошибке/technical details, ожидание total у legacy array `/api/runs`; исправлены локаторы и форма assertion, не приложение. Финальный полный прогон на новой fixture — passed. Изображения отражают синтетические имена и temporary paths, не данные владельца.

## План — UX polish и фактически выполненная матрица

После визуального review UUID убраны из пользовательских заголовков/порядка: шаги пронумерованы и названы. Зависимости выбираются по названиям в native multi-select, с клавиатуры. Технический ID доступен в закрытых details. Удалённая выбранная зависимость не исчезает молча: явно показывается необходимость снять выбор. Подготовка зависимого/несохранённого/устаревшего шага отключена с пояснением; server-side CAS/recheck сохранены.

`themes/results.json`: реально выполнены **18 сочетаний** (9 существующих тем × RU/EN), **108 layout checks** (план, context preview, budget preview × 1440/900 CSS px), 0 pageerrors. В каждом сочетании проверены root-enabled/dependent-disabled до редактирования, Ctrl+Space selection/deselection с сохранением фокуса, отсутствие UUID в видимом плане. Сохранены18 неизменённых PNG. После keyboard edit кнопки ожидаемо требуют явного сохранения, даже если выбор возвращён назад. Визуально просмотрены ru-obsidian-violet и en-light; screenshot корпуса остальных не означает отдельной ручной приёмки каждого пикселя.

Повторение матрицы: после основного сценария на той же fixture `node tests/rc12_plan_matrix.cjs http://127.0.0.1:8768`. Темы/язык меняются только в disposable fixture. Это не Windows DPI, Narrator, WebView2 или реальный аккаунт Codex.

После UI polish:47 targeted Python planning/intelligence tests passed; Node i18n/MC passed; diff whitespace check passed. Эти проверки не прибавляются к полному suite как дополнительные уникальные cases.
