# V2.1 release candidate evidence

## Merge gate

**Native Windows acceptance: NOT VERIFIED. Do not merge under the owner's conditional Windows gate until it is completed.** Linux Chromium, HTTP fixtures, pytest and Docker checks do not establish WebView2, real Windows DPI, installed package or portable package correctness.

Read-only diagnostic script: `packaging/v21-windows-smoke.ps1`. Run it on native Windows with the actual application's loopback URL. It records OS/runtime/API evidence without launching agents or modifying repositories; manual acceptance remains required.

## Source and baseline

PR2 starting HEAD: `064aae8d2f2fee76219069de34ac2cebfae057ff`; remote master: `1d91d21ebd71e9fea17aeb481a935386dcd88b7e`. Before assets were frozen from that HEAD before design changes at `/tmp/codex-v21-before-static`.

Before Chromium screenshots: all nine existing pages and five suite views at 1366×768 Purple Neon, 14 captures (run list and Mission Control share the existing Runs page). Explicit HTTP fixtures, no Codex execution. No JS errors or horizontal document overflow. Evidence: `/workspace/codex-v21-evidence/before-results.json` and `before-*.png`.

Detached PR2 baseline command: `python -m pytest -q` in `/tmp/codex-v21-baseline`; log `/tmp/codex-v21-baseline.log`. Result: **437 passed, 9 failed, 4 skipped**, 1 warning, **82.78 s**. Working-tree changes are excluded from this baseline.

Independent master recheck: `python -m pytest tests/test_runtimes.py -q` in detached `/tmp/codex-v2-baseline` at `1d91d21`: **21 passed, 9 failed**, **1.62 s** (`/tmp/codex-v21-master-runtimes.log`). The same nine runtime failures reproduce on master: base interpreter source; environment narrow-root availability for node/dotnet/java/cargo; PowerShell path hints; generated unittest commands for 0/4/-1. They are not silently excluded from final results.

## Required native Windows acceptance

1. Run both the installed build and final portable build with separate temporary data profiles; reopen the normal profile and confirm existing history/settings/projects remain available. Confirm the shown data directory matches the chosen profile.
2. Confirm official ChatGPT/Codex login remains functional; no separate API key is required. Do not run paid model calls merely to verify layout.
3. Inspect overview, projects/preflight, runs/Mission Control, agents, packs, history, Action Center, usage and settings in every existing theme.
4. At actual Windows 100%, 125%, 150% and 175% scaling, inspect 1024×768 through 2560×1440. Check long Russian strings/Windows paths, dialog scrolling, fixed sidebars and visible focus. Browser CSS zoom is separate evidence.
5. Prepare/edit/save/reopen/approve Task Architect sections; confirm approval is invalidated by edits, duplicate launch is idempotent, and closing during AI preparation cancels/cleans its worker.
6. Create Git checkpoints around tracked changes, preserve staged/unstaged/untracked original files, reject stale recovery preview and recover into a new worktree. Validate retention dry-run and confirm only app-owned checkpoint references can be removed.
7. Set a one-call user budget, reach it using an authorized small task, verify no next agent starts, then explicitly raise budget and resume. Missing token observations must remain unknown.
8. QA without Docker/image must report BLOCKED. Inspect/confirm configured local immutable image and commands. If an explicitly approved setup flow is used, confirm no automatic downloads, host execution or remote inference. Validate real PASS/FAIL/PARTIAL, baseline, logs and report.
9. Exercise Action Center deny/allow within supported scopes, pause/resume/stop, steering, queued instruction, diff/tests/artifacts and restart recovery.
10. Attach script JSON, package versions/hashes, screenshots and actual test results. Mark each unchecked item NOT VERIFIED; diagnostic success alone does not approve merge.

## Current code verification

Final isolated full Python suite: **488 passed, 9 failed, 4 skipped**, 1 warning, **81.13 s**; `/tmp/codex-v21-final-pytest.log`. The nine failures match detached PR2 and master runtime failures above. They remain failures; no unsupported claim of a fully green suite is made.

Independent security review found no critical blocker in the reviewed implementation:

- Task Architect cancellation retains its single ownership slot until execute/interrupt/close finish, keeps its temporary working directory alive while used, and serializes cancellation with its version-checked final save. A late worker cannot write storage itself.
- Checkpoint retention is opt-in and never deletes automatically. Preview expires and binds inventory, references, policy, runs and restores. Run-linked, restored or otherwise reachable checkpoints are protected. Confirmation removes only `refs/codex-team/checkpoints/…` using expected SHA and retains record history; it never calls Git GC/reset or changes user files, index, branches or worktrees.
- QA setup inspects only a local Unix socket or Windows named-pipe Docker endpoint, explicitly supplies `--host`, ignores saved contexts/TLS selectors and rejects TCP/SSH remote endpoints. Image verification requires explicit action and immutable SHA metadata; it does not execute tools, download images or install dependencies. Test execution remains a separate confirmed sandbox operation.
- The local API keeps existing origin/host/JSON mutation restrictions. Transport is shared between old and new screens; external URL spellings, backslashes/control characters and malformed successful responses are rejected; timeouts distinguish offline/cancelled/protocol failures.

Static secret filtering cannot prove absence of arbitrary credentials embedded in normal source text. Same-user malicious filesystem races and a compromised local Docker daemon remain outside a process isolation guarantee. Windows named-pipe operation has code-level checks and mocked coverage, not native execution evidence.

## Persistent screenshot evidence

These screenshots show real Chromium rendering with **explicit HTTP fixtures**, not production projects or live Codex runs. The full matrix additionally includes empty/error/loading fixtures and long Russian task/Windows path content. Browser CSS zoom is labelled separately and is **not Windows DPI evidence**.

| Screen | Evidence |
|---|---|
| Overview before | [PR2 baseline](v21-screenshots/before-purple-neon-workbench.png) |
| Overview after | [Purple Neon](v21-screenshots/after-purple-neon-workbench.png) |
| Runs / Mission Control | [Purple Neon](v21-screenshots/after-purple-neon-runs.png) |
| Action Center | [Purple Neon](v21-screenshots/after-purple-neon-actions.png) |
| Settings | [Purple Neon](v21-screenshots/after-purple-neon-settings.png) |
| Project Intelligence | [Purple Neon](v21-screenshots/after-purple-neon-intelligence.png) |
| Task Architect | [Purple Neon](v21-screenshots/after-purple-neon-architect.png) |
| Budget Guardian | [Purple Neon](v21-screenshots/after-purple-neon-budget.png) |
| Git Time Machine / retention | [Purple Neon](v21-screenshots/after-purple-neon-git.png) |
| QA Arena setup | [Purple Neon](v21-screenshots/after-purple-neon-qa.png) |
| Light overview | [Light](v21-screenshots/after-light-workbench.png) |
| Dark Fantasy runs | [Dark Fantasy](v21-screenshots/after-dark-fantasy-runs.png) |

Screenshot review found a real Runs overflow with long paths: its two-cell rendered row used a three-column CSS layout and unbounded metadata. The corrected two-cell grid/ellipsis is included in final validation. Other reviewed changes include consistent SVG navigation, larger text, common semantic surfaces and clearer task/QA/retention controls.

## Index cache measurement

A 1001-file temporary repository, seven repeated unchanged scans under the same local conditions: before median **232.10 ms** (232.10, 391.13, 419.38, 209.10, 378.66, 213.09, 210.69); after median **194.46 ms** (191.41, 204.00, 200.47, 191.54, 194.46, 191.58, 203.36). Metadata traversal is retained to detect working-tree edits; unchanged file content is not reread. These local observations are not a universal speed claim or a promise for Windows/network repositories.

## Final Chromium result

Command: `NODE_PATH=/tmp/codex-browser-tools/node_modules node tests/v21_browser.cjs after`.

**496 checks passed:** 450 layout checks (15 views, five theme preferences, six viewports: 1024×768, 1280×720, 1366×768, 1440×900, 1920×1080, 2560×1440), 45 CSS zoom checks (125%, 150%, 175%), one explicit visible keyboard-focus check. The 15 views include Runs list and Mission Control as two views of the existing Runs page. No uncaught JavaScript errors, unmapped fixture endpoints or horizontal document overflow remained.

Additional browser scenarios passed: draft survives feature navigation; delayed mutation locks project controls and releases them; 403/no-permission presentation and retry; QA setup verifies metadata without running tools; retention preview with no eligible candidates exposes no cleanup confirmation; explicit AI consent followed by cancellation of a delayed HTTP fixture leaves the editable saved draft. AI inference is not invoked. The final focus probe deliberately focuses the first navigation item before Tab; tabbing out from a removed/end-of-page control is not misclassified as an application focus defect.

[Task Architect editor after cancelled fixture](v21-screenshots/after-architect-cancelled-fixture.png). Full JSON assertion evidence and all screenshots: `/workspace/codex-v21-evidence`; downloadable archive: `/workspace/codex-v21-evidence.zip`.

After final transport hardening, targeted Python UI/server checks passed **27 tests in 5.98 s**. JavaScript syntax and Python compilation checks passed. Windows diagnostic script is supplied for native execution but was not run in Linux; its presence does not satisfy the merge gate.


## Feature and release status

| Component | Implementation | Available verification |
|---|---|---|
| Task Architect | Versioned editable/approved specifications, explicit AI request, cancellation/status API and bounded shutdown with deferred cleanup | 10 lifecycle/API regressions; browser consent/cancel fixtures; real inference NOT RUN |
| Git Time Machine | Existing isolated restoration plus opt-in retention policy, preview and expected-SHA reference deletion | 19 API/Git safety tests; browser dry-run |
| Budget Guardian | Existing measured run/stage usage and backend enforcement retained | Full regression suite; browser dashboard |
| QA Arena | Local Docker setup wizard and immutable image verification; one status aggregator preserves FAIL/BLOCKED through incomplete/cancelled checks | 43 targeted tests including real local Docker smoke; browser setup |
| Project Intelligence | Metadata/Git-aware cache avoids rereading unchanged content, invalidates on HEAD/index/edit/rename/delete | 8 targeted tests and local benchmark |
| Agent Mission Control | Existing run detail remains the single pipeline/inspector/events/diff/tests/artifact view | Synthetic DOM/projection contracts and Chromium matrix |

Confirmed priority findings addressed: **P1** premature Task Architect resource cleanup and uncancelled late results; **P1** FAIL/BLOCKED hidden by PARTIAL; **P2** repeated cached source reads; **P2** missing checkpoint retention controls and QA environment setup; **P2** long-content Runs overflow and fragmented navigation/component styling. No confirmed new P0 finding was identified in the available checks.

Commands/evidence:

- `python -m pytest -q`: 488 passed / 9 known baseline failures / 4 skipped, 81.13 s.
- `python -m pytest -q tests/test_ui_contracts.py tests/test_server.py`: 27 passed, 5.98 s, after final transport changes.
- `CODEX_QA_DOCKER_IMAGE=sha256:53be7ba2c4bbd2afbeb4444161b0073a1616b31fec59b46c5bb798b21854af2a python -m pytest -q tests/test_qa_arena.py tests/test_qa_setup_api.py`: 43 passed, 17.53 s. This environment's explicitly prepared local stdlib-only image was used; no image download or model calls.
- `node --check` for every `codex_team/static/*.js`; `python -m compileall -q codex_team`: passed.
- [Complete browser assertion JSON](v21-browser-results.json). Browser fixture execution does not establish real Codex or Windows execution.

The suite uses additive existing SQLite records/revisions; this hardening adds no destructive schema migration. Retention keeps historical records as tombstones. Packaging includes the new local CSS/JS through the existing static-file wildcard; Windows builds were not produced or accepted here. A defective SDK may finish after the HTTP timeout: the service reserves its single ownership slot and temporary directory until the worker/interrupt/close actually finish, rather than deleting live resources or allowing unbounded concurrent retries.

**Merge is intentionally not performed.** PR #1 is already an ancestor of PR #2; master was not changed. Native Windows 10/11, WebView2, named-pipe Docker, DPI, tray/notifications, installed/portable packaging and existing-data-profile acceptance require the checklist above and real evidence before merging.
