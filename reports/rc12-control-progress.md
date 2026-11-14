# RC12 — Mission Control and factual Budget export

2026-11-14. Baseline 0269b3db6b8d485b6880784f827c9719984aaabb. Shared feature/rc12-product-evolution branch; no commit/push by subagent.

## Implemented

- MissionControl.timeline projects persisted events ordered by ledger ID, deduplicates IDs and excludes explicitly foreign run events. Missing timestamps do not invent timing/progress. Incremental event rendering inserts newly loaded older events in order without rebuilding existing detail nodes.
- Contextual read-only guidance for auth, usage limit, decision, paused, interrupted, failed and stopped runs. Existing explicit action mechanisms remain unchanged; no auto resume/retry or fake percentage.
- BudgetGuardian.export returns a bounded current-page report (max100 via HTTP), project/UTC day filters, total_matching and offset/limit. Unknown measured tokens stay null, real observed zero remains zero, partial usage stays incomplete. Cost/account quota unavailable=null. Excludes task text, workspace paths, raw provider usage, credentials. No SDK/model calls.
- /api/suite/budget/export route, UI explicit preview followed by JSON download. Preview includes scope/privacy limitations and exact frozen rendered report; download does not refetch a different page.
- Date validation rejects invalid/ambiguous ISO day filters. Malformed usage entries yield unknown instead of crashing measured_tokens.
- RU/EN authored text in appended catalog block.

## Ownership

budget_guardian.py; static/mission-control.js; tests/test_budget_export.py; tests/mission_control.cjs. Narrow coordinated edits only to suite_api.py budget route, suite.js showBudget, app.js renderEvents and isolated appended i18n-catalog.js text. Other agent edits in shared files not owned here.

## Actual verification

Linux Python3.12 shared /workspace/.venv-codex:
- pytest tests/test_budget_guardian.py tests/test_budget_export.py tests/test_suite_integration.py -q: **25 passed**, 1 existing Starlette/httpx deprecation warning, 3.17s.
- New export module:9 tests including UTC day/project selection, unknown/zero/partial usage, privacy, bounded pagination, invalid input and real HTTP read-only route.
- node tests/mission_control.cjs /workspace/codex-team/codex_team/static: PASS, including new projection and seven guidance-state assertions.
- node tests/i18n.cjs /workspace/codex-team/codex_team/static: PASS.
- node --check app.js, suite.js, mission-control.js: passed.
- git diff --check: passed at checkpoint.

No Windows, browser visual or live provider test executed by this subagent. Blob download follows existing agent/pack export approach; real WebView2 download behavior requires acceptance. No native host extension, schema migration, permission expansion, budget enforcement change or provider fallback introduced. No all-history aggregate: report and sums explicitly refer to current filtered page. Full regression/release gates remain root-owned.

## Independent review and browser checkpoint

Independent planning review found two defects in control: nextAction(null) could throw during empty selection; malformed persisted usage could still throw in secondary dashboard projections. Both fixed and covered by new regressions. New export module now10tests passed; targeted aggregate previously25passed before adding final malformed-usage case.

Independent review of plan/context implementation found no remaining confirmed blocker in inspected paths: relative bounded files, validated acyclic dependency graph, expected-version writes, source-bound freshness and explicit untrusted-data marker. Final planning includes explicit confirmed root-step handoff; dependent steps are refused and safe options reset before later user launch/queue action.

Actual real-backend browser acceptance: seven scenarios passed, zero pageerrors; genuine PNGs in reports/rc12/browser-planning. See README/results for exact environment/reproduction. No live SDK/model, Windows runtime or complete themes/DPI matrix claimed. Fixture backend stopped after completion.

## Plan UX review follow-up

Root requested polish: now human step headings/order, named native multi-select dependencies with keyboard operation, explanatory disabled prepare for dependent/dirty/stale/unsaved steps, raw IDs in collapsed technical details only. Deleted dependencies retained visibly until user resolves them. Preserved expected-version semantics and second server read after user confirmation. Targeted edits only showPlanEditor; browser selectors updated.

Actual matrix:18 theme/language combinations,108 layout assertions across3 new states and2 widths, keyboard Ctrl+Space and focus checks, zero pageerrors.18 real PNGs and JSON retained under browser-planning/themes. No Windows DPI/accessibility claim. 47 planning/intelligence Python tests pass after polish; Node i18n/MC pass. Fixture shut down.

## Native budget export gap corrected

Review confirmed desktop Blob download cannot be assumed to work: WebView2 global downloads remain disabled/unmodified. Added one narrowly exposed NativeApi operation `export_budget_report(filters)`. It validates project/day/page keys and bounds before HTTP, fetches only the fixed owned backend budget route, opens the existing native SAVE dialog mechanism, and writes bounded backend-owned UTF-8 JSON atomically. JavaScript supplies neither destination nor report bytes. Native cancel/failure never falls back to Blob. Browser mode retains explicit Blob download. Desktop preview explains that native save fetches a fresh server snapshot with reviewed filters.

New contract tests29; combined budget-native/run-report/desktop/services run: **116 passed,1 existing Windows-only skipped**,0.31s on Linux. Covers trusted-origin/ready guard, strict filter whitelist/types/bounds, no HTTP/picker on invalid input, no arbitrary destination/payload input, picker cancel, JSON extension, oversized/malformed report, atomic replacement failure preserving old file and cleaning temp. Existing NativeApi allowlist now explicitly eleven fixed actions.

Real Chromium + real fixture backend with MOCKED pywebview host: five branch assertions passed;3host calls,0Blob calls,0pageerrors; cancel/error/success branches and fresh-snapshot notice. `browser-planning/native-budget-bridge.json` records actual Windows picker NOT VERIFIED. No WebView2 or physical Windows acceptance claimed. Final Windows candidate needs rebuilding from this source. Fixture shut down; no commit/push by subagent.
