# RC12 Task Architect / Project Memory checkpoint

2026-11-14. Branch feature/rc12-product-evolution. Implementation is uncommitted, source-based on Codex Team RC11; no release or live AI call claimed.

## Delivered

- Separate `specification_plan` versioned records using existing SuiteStore; no destructive migration. Up to20 editable steps with title, acceptance, relative file declarations and explicit dependency IDs. Rejects cycles/missing IDs/duplicates/invalid paths; computes deterministic topological order, shared file warnings and root candidates. Candidates are **not proven independent**. No implicit queue/start/model call. Plans become stale when specification version changes; writes require current spec version and compare-and-swap for existing plans. Plan save does not silently approve or launch the main specification.
- Knowledge save captures current HEAD and bounded source SHA256 digests. Listing reports current/stale/review_required/unknown without mutating record versions. Source edits/deletion/untracking/ignore invalidate factual context even before commit; unrelated HEAD changes retain matching source facts. Sourceless decisions require review after HEAD changes. Legacy records retain their text and editable state, but have unknown freshness and are excluded from automatic context until explicit review/save.
- Context preview has query +512–12000character bound; returns exact generated payload, size and model_called=false. Explicit trust label says project data is untrusted, not system instructions. Existing context flow excludes stale/unknown knowledge.
- Real UI: editable Work Plan inside Task Architect; source freshness badges and explicit context-preview form inside Project Intelligence. Authored labels RU/EN; no JS injection (textContent controls). No app.js/storage.py changes by this task.

## Files

codex_team/task_architect.py; codex_team/intelligence.py; targeted additions in suite_api.py and suite.js (other agent independently owns budget sections); tests/test_rc12_planning.py.

## Actual checks

`/workspace/.venv-codex/bin/python -m pytest tests/test_rc12_planning.py tests/test_intelligence.py tests/test_task_architect.py -q`: **45 passed,0failed**,5.04s,1 upstream Starlette TestClient/httpx deprecation warning. Real FastAPI/Git/SQLite integration verifies plan/context routes, bounds and no dispatch; client cannot inject source-binding metadata. Node parse suite.js passed; tests/suite_messages.cjs passed.

No live SDK call, full suite, browser/WebView2 or Windows runtime check performed by this task yet. Parent will integrate common release tests. All new plans are advisory and never turn the independent mission queue into a dependent executor.

## Follow-up review / explicit step handoff

Root review requested selected independent-candidate handoff, not just advisory plans. Implemented `GET /specifications/{id}/plan/prepare` bound to exact saved plan version and current specification version. Dependent/missing/stale steps are rejected. A row action prepares the selected root step in the existing main composer only after replacement confirmation. Server revision is checked again after the dialog; a changed/conflicted composer aborts replacement. Access resets to workspace, isolation on, auto-commit off; actual launch or normal queue-add/preflight remains a separate existing user action. No dependent batch, auto-start, model call or permission escalation.

Narrow `app.js` bridge addition was coordinated with parent; control agent edits only renderEvents. Plan reads now hold existing store lock while comparing specification+plan; missing HEAD is unknown, never current. Targeted suite after these backend additions: **47passed,0failed**,5.35s,1 upstream deprecation warning. `git diff --check` and JS parsing pass.

Independent review of control agent: confirmed `nextAction(null)` TypeError and malformed persisted usage projection hazard; reported both to owner for fixes/regressions. No concern found in bounded current-page export, exclusion of task/path/rawusage and null/real-zero distinctions.

Executed all15 existing Node scripts directly with absolute static path: ui_smoke,mission_control,api_client,i18n,suite_messages,pack_localization,refresh_loop,task_drafts,command_palette,task_templates,run_comparison,run_notebook,run_replay,mission_queue,project_doctor — **all PASS**. Initial direct invocation used relative path incompatible with require() in MissionControl harness; corrected invocation, not a product failure. No tests disabled.

## Frozen-runtime acceptance additions

Added `packaging/smoke_evolution.py`, invoked by actual extracted-portable smoke during startup/restart and installed smoke during startup/repair-restart. It calls the real frozen loopback HTTP backend; checks bounded private-text-free current-page Budget export, saves a synthetic two-step plan, verifies independent prepare succeeds/dependent prepare fails, validates512-character untrusted context preview, and compares saved runs/queue before/after to exclude dispatch side effects. Restart uses the saved specification ID, requiring actual persistence rather than recreating a fixture. CLI refuses non-Windows/non-GitHub-Actions execution and non-loopback URLs. Existing parent smoke owns isolated temporary profiles/projects and all original gates remain.

New required keys for both native reports: `evolution_budget_export_verified`, `evolution_plan_verified`, `evolution_context_preview_verified`, `evolution_no_dispatch_verified`, `evolution_plan_restart_verified`. Root owns workflow enforcement. These flags start absent and become true only after actual assertions; no Windows PASS claimed before native run.

Source-side real FastAPI protocol tests + existing portable archive tests pass. An initial combined packaging/workflow check had20passed/1failed because RC12 release notes omitted existing literal RU/EN/theme compatibility labels; root notified to correct documentation, not tests. Native run must use the final commit containing these hooks.
