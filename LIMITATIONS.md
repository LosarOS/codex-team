# Ограничения 1.0.0-rc1

- Один writer; specialists последовательные. `max_parallel_agents` не означает реализованные parallel coding tasks.
- Нет automatic updater, push/merge или автоматического удаления worktrees.
- Bundle содержит stdlib Python, не dependencies всех проектов; другие language runtimes внешние.
- Native QA ledger подтверждает узнаваемый completed exit0 suite с ненулевыми tests. Это не доказательство test relevance или защита от намеренно подделанного output. Unsupported wrappers/custom runners могут потребовать решения; failed suite даже с успешным retry в том же turn консервативно блокирует completion.
- Secret filename guards/redaction не гарантируют обнаружение всех secrets. Native pre-start deny expansion depth16 ограничена; новые sensitive files требуют осторожности.
- API execution проверен mocks; real API inference/paid calls не выполнялись. Fake key использован только для Windows secure-store round-trip с cleanup.
- NotifyIcon balloons зависят от Windows notification settings. Application artifacts unsigned. Windows 10/11 — target platform, не доказательство тестирования всех сборок/машин.
- Baseline installed DONE/Resume/reinstall и source native smoke не заменяют final polished installer acceptance. Итоговый статус смотрите в release reports.
