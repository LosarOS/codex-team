# UI/UX audit and Windows acceptance

Source baseline: `1d91d21ebd71e9fea17aeb481a935386dcd88b7e` (`master`).
This report distinguishes source/fixture checks from Windows acceptance. No live
Codex generation or paid API call is required for the checks in this change.
The existing final-release report remains historical evidence, not a new pass.

## Scenario and dependency map

| Section | Main scenario and backend dependency | Important boundary states |
| --- | --- | --- |
| Обзор | Choose registered/local Git project, task, mode/pack; `POST /api/runs` → Engine.create/launch | No project/auth; dirty/no-commit Git; invalid pack; duplicate submit; slow/offline backend |
| Проекты | Native folder picker or typed path; Projects.inspect/preflight; commands/diff | Missing repository/runtime; dirty tree; long Windows path; stale project; save/remove without removing files |
| Запуски | Summary list → full persisted run → events/diff; Engine.control | Sequential stages, repair/retry, pause at stage boundary, stop, interrupted/auth/limit/error; stale selection responses |
| Агенты | Registry agents; per-agent model/instruction CRUD/import/export | Built-ins protected from delete; explicit write/network confirmation; missing/disabled role; long instructions |
| Наборы | Registry packs and pipeline validation | Built-in protection; custom role references; required roles by mode; read-only specialists; duplicate names |
| История | `GET /api/runs?summary=true` pagination/search/archive → run/resume | Empty/profile mismatch; filters, archived data; checkpoint/worktree deleted; interrupted recovery |
| Центр действий | Durable action cards → Engine.resolve_action → live SDK waiter or product resume | Expired/superseded requests; only allowed decisions; high-risk confirmation; unsupported grants; double click/offline |
| Использование | Account `/api/usage` separately from run.usage/usage_total | Unknown usage is unknown; cached/input/output fields; last-20 summary scope; account/provider unavailable |
| Настройки | Partial Settings merge; explicit provider choice; official auth; native bridge | Theme/system/accent; draft preservation; model discovery unavailable; explicit separate API billing; no fallback |

Frontend state lives in `static/app.js`; SQLite persists runs, actions, settings,
projects, agents and packs. Registry seeds editable resources. Provider supplies
SDK transport/events; Engine owns one active writer and validates checkpoints.
DesktopRuntime owns the local backend/process tree; DesktopBridge exposes fixed
native actions only to the trusted local page. NotificationLedger deduplicates
native notifications. SessionMarker and Store.recover preserve interrupted work;
pending SDK approvals expire rather than approving a replacement SDK session.

## Confirmed findings

No newly proven P0 data loss or permission defect was found in this source audit.
An RC history/profile blocker remains unverified, described below.

| Priority / source | Reproduction and actual vs expected | Correction / evidence |
| --- | --- | --- |
| P1 — `static/app.js`, control/refresh/poll | A control request races with an older full-run refresh: selectionVersion alone identifies the same run, so the older response can overwrite newer state. Expected: accepted control state survives older responses. | Guard with a run revision and coordinate control/poll pending work; regression checks accompany UI changes. |
| P1 — `static/app.js`, fetchEvents / more-events handler | Reject the events API after clicking “more”: the click returns an uncaught Promise and there is no dedicated retry/error state. Concurrent clicks can fetch the same cursor. Expected: one in-flight request and recoverable error. | Single-flight event loading, error/retry feedback and disabled loading button. |
| P1 — `static/app.js`, renderConnection / renderRun / control | Delay a create/control POST, then refresh status/details. Rendering can re-enable its buttons and submit the operation twice. Expected: mutation stays single-flight through all renders. | Independent pending guards for creation/control/action IDs; held-response duplicate-submit tests. |
| P1 — `static/app.js`, resolveAction | Resolve action A, hold the subsequent full-run GET, select run B, then release A. Baseline assigns A without rechecking selection. Expected: B stays open. | Selection check after the awaited detail response; cross-run held-response regression. |
| P2 — `static/app.js`, renderActions | Enter an answer/budget on request A; update a different pending request B. Whole-list replacement destroys A's input. Expected: unchanged requests retain drafts. | Reuse unchanged action cards by ID and signature; regression verifies card identity and draft value. |
| P2 — `static/app.js`, renderActivePipeline / renderInspector | A role executes again after repair: baseline deduplicates roles and reads latest role-keyed results, hiding prior attempts and planned rechecks. Expected: each recorded call and future pipeline slot is inspectable. | Project calls from chronological stage events/result_history; distinct attempts and future repeated roles, with no fabricated timestamps or progress. |
| P2 — `static/app.js`, renderEvents | Each new page replaces every event DOM node, even when earlier rows are unchanged; an open/focused row loses node identity during polling. Expected: append new rows and retain existing interaction/scroll. | Reconcile rows by event ID, preserve scroll and expanded DOM nodes. |
| P2 — `desktop_services.py`, DiagnosticBundle.collect | Export diagnostics when installed history is empty. Baseline archive has no selected profile/database identity or history count; cannot compare chosen profiles from the archive. Expected: enough metadata to identify the actual profile without exporting history. | Add redacted root/database path, database existence and all-runs count from existing summary API. Offline count stays null. Focused tests verify redaction, no task export, and no database creation/modification. |

Visual and browser findings/validation are recorded separately in the delivery
report; a source inspection alone does not establish pixel-level correctness,
WCAG conformance, or completion of every section/state combination.

## Mission Control data contract

No new execution/permissions backend is necessary. Use full run.pipeline,
run.stage/current_role/state, role snapshots, result_history, results, executions,
changed_files and usage. Events expose agent_started (iteration/call),
agent_completed (verdict/summary), commands, repair_requested, user_instruction,
action_required/resolved, pause/stop requests and final run_state with timestamps.
The existing meaningful event endpoint has after/limit/next_cursor/has_more.

Pipeline roles are sequential and can change after coordinator specialist
selection or repair rechecks. Attempts must be identified chronologically,
including repeated starts in the same iteration after a resume. Latest role-keyed
results/executions cannot be assumed to describe every historic attempt. Missing
start/end times, usage or outcomes must remain unknown. Backend elapsed_seconds
is accumulated when a worker finishes; it is not a continuously updated clock.
Pause requests do not immediately change persisted RUNNING to PAUSED. Native
permissions must continue through Action Center allowed_decisions and live SDK
request checks. Product resume is not a native grant.

## Existing RC risks and exact Windows acceptance

The source root-selection order is explicit `--data-root` (launcher), then
`CODEX_TEAM_DATA_ROOT`, then a validated portable marker beside the frozen EXE,
then `%LOCALAPPDATA%\\CodexTeam`. Legacy migration is explicit via
`--legacy-root`/`CODEX_TEAM_LEGACY_ROOT`; no automatic scan/merge of unrelated
profiles occurs. Installed and portable profiles intentionally differ. Unit tests
cover selection, migration backup and malformed-marker rejection, but do not
reproduce the reported installed-profile history mismatch.

Before merge/release, on Windows 10/11 x64 with WebView2:

1. Back up each known data profile with the application closed. Record launch
   shortcut target/arguments, `CODEX_TEAM_DATA_ROOT`, portable marker presence and
   version. Do not delete or merge profiles to make empty history disappear.
2. Export diagnostics from the old and candidate launches. Compare data_profile
   root/database/run_count (USERPROFILE is redacted). With the app closed, compare
   `SELECT count(*) FROM runs` in read-only copies of each database and known run
   IDs. Resume a known unfinished run from the intended profile; verify completed
   stages, history, settings and prompts remain. Unknown/offline count is not zero.
3. In the final installed package run official ChatGPT login, choose a clean
   committed Git project, start a small authorized task and inspect Mission
   Control, diff, test evidence, artifacts and per-run usage. Test native approval
   allow-once/deny/high-risk confirmation, expired request after restart, and
   product resume separately. These live SDK checks were not run in Linux.
4. Request pause during a stage; verify it stops after that stage. Queue/steer a
   Russian instruction; resume, then stop. Restart after a controlled interruption
   and verify partial edits/checkpoint protection. Never modify real user work
   solely for this test; use a disposable committed repository.
5. Test Light/Dark/Purple Neon/Dark Fantasy/System with keyboard Tab/Shift-Tab,
   Escape, dialog focus/return, disabled controls, error/retry and long paths/tasks.
   Inspect 1024×768, 1280×720, 1366×768, 1440×900, 1920×1080, 2560×1440 at Windows
   100/125/150% and, if available, 175% DPI. Browser viewport emulation is not
   Windows DPI acceptance.
6. Test tray close: keep running, stop/exit, cancel; notification click opens the
   correct run; restart deduplicates old notifications; backend crash/retry works.
7. Repeat startup/history/resume/close with the final portable ZIP (all bundled
   files retained). Compare its adjacent data profile with the installed one.
   Validate final installer upgrade/uninstall retains data and official login;
   verify no owned backend/SDK child remains after exit. Do not claim final
   package acceptance from source-only browser fixtures.
