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

## Checkpoint — Windows archive boundary and real backend UI

Windows native run40004056526 correctly blocked packaging:874passed,1failed,1skipped,641.34s. The new archive test expected a literal backslash, but Python's Windows ZipInfo normalizes names; the test fixture and reader needed to preserve/check the original central-directory name. Fixed in `57e1aa6`: inspect `orig_filename`, construct/assert a real raw-backslash archive and simulate Windows normalization in an additional regression. Focused26passed; no test disabled. Archive/publication guards now run early before the full suite. Superseded known-ineligible native run40004337154 was canceled; corrected [40005922301](https://github.com/LosarOS/codex-team/actions/runs/40005922301) is authoritative when complete.

[Source CI40005929916](https://github.com/LosarOS/codex-team/actions/runs/40005929916), source57e1aa6: **874passed,4skipped,1warning,82.05s**, Node UI smoke and Doctor/preflight contracts passed.

Additional real-backend product review used actual FastAPI/SQLite/Engine and Linux system Chromium, with no mocked HTTP routes or provider substitution. Seven functional assertions passed: registered SHIFT Doctor found six projects and correct provenance/unverified gates; closing returned keyboard focus; explicit UI enqueue saved one pending mission; actual preflight reported models_called=false/provider_verified=false; reload did not start it; RU/EN and Obsidian/Neon settings persisted.173actualbrowserrequests,0JSerrors,0missionstart/runcreationrequests, actualrunslistempty.

Four real `/api/providers` HTTP400 responses were preserved and reproduced: Windows Credential Manager is unavailable on Linux. A visible refresh warning is therefore expected in these Linux screenshots; they are not Windows/WebView2 acceptance. The server PATH also lacks dotnet even though a separate SDK exists outside PATH, and preflight correctly requires attention. No tools were installed silently. The isolated server was shut down normally.

P2 product follow-up: compact the long preflight check list and repeated mission text while retaining raw technical evidence. Do not hide the local-tool/auth limits or imply that preflight predicts provider success.

## Final review and merge — 19:31 UTC

PR16 merged as `4c3c91eb6f6e682745569b8fd7d2ffdf39fbe595` after source CI at `ad550494608db072008166aa357df86429d5cd0f` passed **874 tests / 4 skipped** and native Unicode shortcut positive/negative checks passed. Independent packaging review found no remaining blocker in source binding, hash/size checks, native smoke flags, skipped-suite rejection or draft-first publication.

[Diagnostic native40010564404](https://github.com/LosarOS/codex-team/actions/runs/40010564404) passed actual frozen packaging, extracted portable/restart and expanded installed/shortcut/repair/uninstall/preservation/reinstall checks. Its full source suite was explicitly skipped to isolate the corrected shortcut reader. Its artifacts are **ineligible for release**. The final full master push build is [40011993846](https://github.com/LosarOS/codex-team/actions/runs/40011993846); publication remains blocked until that complete run succeeds.

The diagnostic bundle checked49 required files out of3218; official CLI0.162.1, bundled Git2.56.0.windows.2, Python3.12.10. This is Windows backend/packaging evidence, not interactive WebView2 acceptance. No inference was performed by native smoke.

Documentation review found stale RC1 installation/history/updater statements in the current user guide. Updated guide, limitations and release checklist distinguish current evidence, historical reports, manual updater and remaining GUI gates. Raw cross-project summaries and real-backend browser results are retained in `reports/rc11/`; no credentials, private data roots, invented diffs or zero-filled token metrics are published.

P2 follow-up: compact long preflight cards, then conduct physical Windows10/11 WebView2, DPI/text/keyboard/screen-reader and GUI portable-profile acceptance. P3 visual experimentation remains deferred. No schema migration, permission expansion, automatic retry/merge or paid API fallback was introduced.

## Public RC11 release — final checkpoint

Status: **VERIFIED PRERELEASE WITH DISCLOSED LIMITATIONS**. [Public release](https://github.com/LosarOS/codex-team/releases/tag/v1.0.0-rc11), binary/tag source `4c3c91eb6f6e682745569b8fd7d2ffdf39fbe595`. PR16 merged; no source schema migration or permission expansion.

- [Final full Windows master build40011993846](https://github.com/LosarOS/codex-team/actions/runs/40011993846): SUCCESS, Windows Server2025 x64 / Python3.12.10. **877 passed,1 skipped,1 deprecation warning**, pytest957.85s (JUnit957.749s). The22 early packaging tests are a subset, not an additional total. Only the opt-in Docker case skipped.
- [Publication40015374294](https://github.com/LosarOS/codex-team/actions/runs/40015374294): SUCCESS. Downloaded the successful push artifact, enforced native gates, uploaded draft, re-downloaded GitHub binary assets and verified SHA256 before publication.
- Independently downloaded all three public binaries without a GitHub credential: HTTP200, exact nonzero sizes, SHA256 matched published SHA256SUMS and GitHub asset digests. Tag resolved to the same binary source. [Machine-readable proof](rc11/public-release-verification.json).

| Asset | Bytes | SHA256 |
|---|---:|---|
| CodexTeam-Portable-x64.zip | 249646520 | 027644b7edf053d282536a74c1385938a531a0644dab68d8d565594ea2534006 |
| CodexTeam-Setup-x64.exe | 155639105 | 7ae495f8aefa402205496b8a83a10159561528e1a42c7d7c52b06480ed1ed82f |
| CodexTeam-Setup-x64.zip | 155173867 | 40e22d858ae887e7badfc1d697d6f0e7975699b3a583ff2b81259688de20e2f7 |

Public `installed-smoke.json` independently inspected: real installed backend, Start Menu Unicode target/directory, Doctor, queue preflight, same-version repair, settings/history/notes/drafts/templates and pending queue restart, updater check, uninstall/profile preservation and reinstall/restart are true. Public portable proof confirms archive CRC, extracted frozen startup/restart and settings/history/pending queue preservation. Both record zero model/account calls. The saved history fixture is explicitly synthetic.

`native_gui_verified=false` and `gui_portable_marker_selection_verified=false` remain explicit. No interactive WebView2/physical Windows10/11/DPI/Narrator acceptance or successful live SDK development is claimed. Same-version repair is not exhaustive older-release migration. Unsigned binaries may trigger SmartScreen. [Manual release checklist](../docs/RELEASE_CHECKLIST.md).

Final source CI remains874passed/4skipped on Linux Python3.12.14; Node/UI contracts passed. Browser fixture matrix216 combinations and seven real-backend functional checks retain the environment limits above. Advisory lookup:40 exact desktop pins, zero known findings after the two dependency updates; not an exhaustive native/OS security audit.

The final documentation-only follow-up updates the current user guide, limitations/checklist, historical-report notice and sanitized evidence. It does not rebuild/replace any published asset, move the release tag or change application code.
