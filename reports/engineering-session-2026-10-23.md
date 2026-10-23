# Operation Double SHIFT — Codex Team

## Baseline and plan

- Base/master SHA: `dc272e0dd87cb86bb8a7ca48bd5594757e55db5d`; clean tree confirmed.
- Branch: `engineering/double-shift-rc11`; dedicated checkout and disposable test data.
- Latest release: `v1.0.0-rc10`; no open PRs at initial audit.
- Last native [release CI](https://github.com/LosarOS/codex-team/actions/runs/39328783236) succeeded at `f9c5dfd2e7fcef28578e3d7d927651b8d357349e`.
- Existing report: Linux 828 passed/4 skipped, Windows 831 passed/1 skipped. These are prior results, not reruns in this session. Live SDK and interactive WebView2 remain unverified.
- Target: `1.0.0-rc11`, preserving current binary asset names and schema compatibility.

## Audit checkpoints

Architecture: existing Engine, WorkspaceManager, Store, MissionQueue and native lifecycle stay authoritative. Queue has explicit start, frozen IDs, project budget snapshot and no automatic restart/merge. New diagnostics must not bypass those boundaries.

| Priority | Finding / evidence | Planned action |
|---|---|---|
| P1 feature | Existing queue reason is free text; distinct outcomes are not structured in API | Structured blocked diagnostics preserving actual state and technical reason |
| P1 feature | Queue lacks a separate read-only batch preflight | Inspect local project/isolation/tools and snapshot without provider calls or mutations |
| P1 feature | No dedicated Windows/.NET Project Doctor | Bounded tracked-file discovery, source provenance, separate build/publish/installer/GUI gates |
| P1 verification | Actual ChatGPT/Codex integration not yet confirmed | Use official authentication checks and isolated SHIFT mission; no paid API fallback |
| P2 release | Workflow hardcodes RC10 notes/screenshots | Stage current-version evidence without presenting old screenshots as new |

## Execution order

Audit production paths → Project Doctor → queue diagnostics/preflight/UI → focused and full suites → bounded real integration → Windows packaging/preservation → PR/merge/release and published asset hashes.

Next: inspect project safety, API/UI conventions and queue tests; prepare isolated Python environment. No new release is claimed by this report.

## Checkpoint — diagnostics and queue (12:16 UTC)

Implemented bounded read-only Project Doctor with an explicit project action, RU/EN panel, environment/declaration provenance, separate unverified compilation/publish/installer/GUI gates and structured report. No project commands or model calls are executed. Added 13 backend cases covering malformed input, XML entities, exclusion boundaries, Unicode, read-only behavior and API contract.

Queue now exposes structured blocking categories and linked state, performs explicit read-only local preflight, and guards confirmation with a revision hash. Existing explicit dispatch, immutable budgets, isolation, idempotency and no automatic retry remain authoritative. Confirmed P1 reliability defect: reorder persisted two positions separately; fixed with one SQLite transaction, tested with an injected second-row failure and rollback.

- Focused backend: **55 passed** (Project Doctor + queue and API; Linux Python 3.12).
- Existing Node UI smoke: PASS, 288 IDs / 142 fixture fetches; queue and new Doctor contract checks PASS.
- Chromium HTTP-fixture matrices: **54 queue + 54 Doctor combinations**, 9 themes × RU/EN × 3 sizes; no JS errors, unknown endpoints, checked untranslated labels or horizontal overflow. These are not Windows WebView2/DPI acceptance.
- Full Python collection initially blocked by missing test-environment `psutil`; installing the existing pinned desktop requirement, not suppressing the test. Current full suite running with pinned Starlette/Pydantic versions.
- Browser logs/screenshots are local fixture evidence in the session scratch directory; no generated screenshots are presented as a real model run.

Next: full regression, native Windows workflow on PR, live official SDK availability, then final release gates. Release remains BLOCKED pending these checks.

## Live SDK experiment — authentication boundary

- Source: SHIFT `a8bfe05b7c5ede8c465a269e4c19285339dd69e1`, cloned separately; Engine created its own worktree.
- Actual run `run_77db24332f14`, Implement, standard permissions, isolated=true, auto_commit=false, 4-call / 1200-second / 80000-token ceiling. Task: regression tests for FileLog HRESULT, safe method frames and graceful I/O failures.
- Official SDK account-read reported `CONNECTED`, ChatGPT account, API key not required. The first actual coordinator turn failed because the access token could not be refreshed after logout/account change.
- Observed wall time 3.44 seconds; recorded Engine elapsed 3.383 seconds; 1 attempted agent call. Token usage unavailable (not zero). No developer/QA/reviewer execution, no changed files, no integration diff accepted.
- Live development result: **NOT VERIFIED — authentication blocked**. No paid API fallback attempted.
- Confirmed product defect: this exact SDK error was categorized `AGENT_FAILED`/`FAILED` rather than `AUTH_REQUIRED`. Added exact refresh-failure classifications and regression cases; provider suite **66 passed**.

## GitHub checkpoint

- PR: https://github.com/LosarOS/codex-team/pull/16 (draft).
- Native RC11 build: https://github.com/LosarOS/codex-team/actions/runs/39951850503 (publication disabled).
- Source PR CI: https://github.com/LosarOS/codex-team/actions/runs/39951853858 passed.
- Production-backend asset regression caught missing Doctor CSS/JS allowlist; fixed and included both assets in frozen/installed checks. Focused regression **65 passed** after fix.

## Checkpoint — 12:39 UTC, combined source 93736d0

- Full local regression before final UX/packaging additions: **859 passed, 4 skipped**, 64.52s. Skips: Windows child presentation, two NTFS junction cases, opt-in pre-existing Docker image. Docker is not a product requirement and no image was installed for this session.
- Independent provider/Engine/queue/permission review: **174 passed, 1 skipped**; refresh-auth classification does not retry, switch provider or expand access.
- Final UI fixture matrices: **144 queue/preflight + 72 Doctor combinations**; keyboard Tab/Enter, stale reports, delayed replies, current-card focus restoration and per-card bounds verified. Linux Chromium fixtures, not Windows/DPI evidence.
- Pinned desktop dependency audit originally found 36 advisories across certifi/Pillow. Updated certifi2026.10.23 and Pillow13.0.0, verified Windows wheels and regenerated icons in a disposable directory. Repeat audit: **40 packages, zero known advisories**. Details: [packaging validation](rc11-packaging-validation.md).
- Native baseline [39951850503](https://github.com/LosarOS/codex-team/actions/runs/39951850503) **SUCCESS** at source1364c38; real frozen Windows package and prior installed/backend/uninstall smoke. This does not validate later fixes.
- New final native gates add installed Doctor/preflight endpoints, explicit disposable-CI/existing-install guards, same-version repair, uninstall profile preservation, reinstall/restart/history/settings/queue preservation. Native JUnit counts and exact source SHA are staged with final artifacts.
- Release publication now verifies GitHub-downloaded asset hashes while a draft, then publishes. Artifact-only workflow rejects missing RC11 evidence and skipped source suite.

Next: final combined source regression and Windows build, PR review/merge if green, then GitHub prerelease with actual downloaded asset hashes. Live SDK development remains authentication-blocked pending owner’s official re-login; the attempted run and absent metrics remain disclosed.

## Checkpoint — final source regression, ced1aec

Final Linux Python3.12 regression at frozen source `ced1aecac1569150cb0d9f1dfabf5979eaaac246`: **873 passed,4 skipped,1 deprecation warning,62.14s**. Skips remain the Windows child presentation, two junction cases and explicitly opt-in Docker image test. Node/UI fixture results above remain applicable. During an earlier overlapping edit/test run, the test process retained an older fixture while reading the newly edited workflow; the mixed verification failed. Re-running the unchanged focused test and full suite after freezing source passed; no test was disabled or weakened.

Confirmed release-version defect: `desktop_runtime.VERSION` still hardcoded RC10 while package metadata was RC11. It now imports the package version; regression checks bind desktop/session/backend version to that source. Installed and portable smoke plus fallback publication also reject mismatched runtime version.

The final branch native run is [40004337154](https://github.com/LosarOS/codex-team/actions/runs/40004337154), full source suite enabled and publication disabled. It includes extracted-portable backend/start/restart, Unicode temporary paths, bundled Git discovery, history/settings/queue preservation, Start Menu target, installed repair/uninstall/reinstall and runtime-version gates. Outcomes must be taken from the completed run and staged evidence; queued checks are not PASS.

## Cross-project auth regression after the fix

Actual Engine run `run_3f8712c9e45e` against SHIFT `e054cd00e3d73cf815bae2b1280b98d8d45f01ea` used Implement, standard, isolated=true, auto_commit=false,4-call/1200-second/80000-token limits. The task was bounded uppercase EXE/LNK Doctor regression tests. Engine created a real worktree; the first official SDK turn again encountered the stale refresh token. This time the final state is correctly **AUTH_REQUIRED**. One attempted coordinator call, elapsed1.684s, wall1.74s. Usage and changed-files metrics unavailable, no developer/QA/reviewer output or accepted diff. No paid API fallback. Live AI development remains **NOT VERIFIED** until official ChatGPT/Codex re-authentication and a successful bounded mission.
