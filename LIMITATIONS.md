# Ограничения 1.0.0-rc11

- Один writer; specialists последовательные. `max_parallel_agents` не означает реализованные parallel coding tasks.
- Нет фонового автоматического обновления, push/merge или автоматического удаления worktrees. Обновление запускается пользователем через `Обновить.cmd`; см. [инструкцию](INSTALL_WINDOWS.md#обновление-из-github).
- Bundle содержит stdlib Python, не dependencies всех проектов; другие language runtimes внешние.
- Native QA ledger подтверждает узнаваемый completed exit0 suite с ненулевыми tests. Это не доказательство test relevance или защита от намеренно подделанного output. Unsupported wrappers/custom runners могут потребовать решения; failed suite даже с успешным retry в том же turn консервативно блокирует completion.
- Secret filename guards/redaction не гарантируют обнаружение всех secrets. Native pre-start deny expansion depth16 ограничена; новые sensitive files требуют осторожности.
- API execution проверен mocks; real API inference/paid calls не выполнялись. Fake key использован только для Windows secure-store round-trip с cleanup.
- NotifyIcon balloons зависят от Windows notification settings. Application artifacts unsigned. Windows 10/11 — target platform, не доказательство тестирования всех сборок/машин.
- Project Doctor читает ограниченный набор отслеживаемых Git-файлов и не вычисляет MSBuild. SDK и команды обнаруживаются без их запуска; это не успешная сборка, publish или GUI-приёмка. Preflight очереди не проверяет авторизацию, квоту или будущий результат модели.
- Автоматические native проверки backend, установки, restart, repair/reinstall и сохранения профиля не заменяют интерактивную WebView2-приёмку, проверку portable-профиля через GUI и DPI/accessibility на Windows 10/11. Same-version repair не доказывает миграцию со всех старых версий. [Итоговый отчёт RC11](reports/engineering-session-2026-10-23.md).
- В этой сессии две реальные изолированные задачи SHIFT дошли до официального SDK, но остановились из-за устаревшей авторизации ChatGPT/Codex. После исправления классификации конечное состояние — AUTH_REQUIRED. Разработка через живого агента, QA/review его diff и расход токенов не подтверждены; платный API вместо подписки не использовался.
