# Codex Team 1.0.0-rc1

RC добавляет executable bundled Python/stdlib, проверку project runtimes, Action Center, agent/pack editing, explicit optional API provider с secure key store, tray/notifications, active-close choices, recovery banner, native ID-only project/worktree opening, safe navigation и allowlisted diagnostics ZIP. Portable и installed state разделены. Default ChatGPT/no automatic billing fallback сохраняется.

## Фактическое evidence

- `reports/runtime-regression.txt`: baseline full suite **321 passed, 3 skipped**, один Starlette warning.
- `reports/runtime-baseline-acceptance.json`: installed runtime checkpoint `run_d2f711468518` **DONE**, Developer IMPLEMENTED / QA PASS / Reviewer APPROVED, семь calls. Resume не повторил completed Coordinator/Analyst; normal close завершил восемь tracked owned процессов.
- `reports/runtime-native-qa.json`: реальные completed exit0 QA suites с **4 и 7 tests**; inspection отделены от tests.
- `reports/uninstall-reinstall.json` + baseline acceptance: settings/history/checkpoint/official auth сохранены.
- Desktop polish focused tests: **71 passed, 1 skipped**. `reports/desktop-native-rc-smoke.json`: actual source CLR tray visible/disposed, remote/file document navigation blocked, redacted ZIP и unique fake Windows credential round-trip/delete PASS; без model/API calls.

Baseline/source checks не подтверждают final polished installer сами по себе. Final build/install/portable acceptance и hashes фиксируются отдельно в [release checklist](docs/RELEASE_CHECKLIST.md). Application unsigned; реальные API inference не выполнялись. Остальные границы: [LIMITATIONS](LIMITATIONS.md), [SECURITY](SECURITY.md).
