# V2 five-feature validation

This report distinguishes detached `master` baseline, changed-branch tests, Chromium HTTP contract fixtures, live FastAPI fixtures, and native Windows acceptance. No paid inference or live Codex execution is used for QA.

## Baseline

Command: `python -m pytest -q` in detached master worktree `/tmp/codex-v2-baseline`.
Result: **389 passed, 9 failed, 3 skipped**, 1 warning, 215.49 seconds. Full log: `/tmp/codex-v2-baseline.log`.

Existing failures all belong to `tests/test_runtimes.py`:

- `test_source_uses_base_interpreter_not_application_executable`
- `test_environment_tools_have_narrow_roots_and_clear_availability` (node, dotnet, java, cargo)
- `test_powershell_hints_escape_paths_and_do_not_interpolate_repo_script`
- `test_generated_unittest_command_really_runs_current_workspace_without_bytecode` (0, 4, -1)

The V2 working branch includes prior Mission Control work to preserve that implementation; baseline above is explicitly master, not an assertion that the branch is identical to master before V2.

## Independent security review

Reviewed actual production service code rather than UI labels:

- Intelligence uses tracked, bounded text files, rejects sensitive paths, ignored tracked files, binaries and symlinks; source reads use containment checks. Knowledge categories stay separate and AI suggestions are excluded from automatic context.
- Task Architect requires explicit Codex consent, rejects the optional paid provider, validates edited section shape and approved versions. Review identified possible native-tool exposure through source cwd; implementation was changed to an empty temporary directory with bounded context in the prompt. Shell execution is disabled. Fake-provider tests do not constitute live SDK E2E.
- Time Machine uses a temporary index, private refs, no hooks/fsmonitor, and tracks existing Git files only. Recovery requires matching preview and confirmation, and creates a fresh worktree/branch. Original HEAD, index and dirty/untracked work remain intact. Secret-looking tracked paths, symlinks and submodules are blocked conservatively.
- Budget policy is enforced at backend stage boundaries; observed run token usage is distinct from unknown account quotas. An in-flight SDK call cannot be retroactively limited by a next-stage guard.
- QA Arena never falls back to executing project code on the host; commands run in an explicitly chosen local immutable Docker image without network, extra capabilities or writable host source. Preview binds code digest and configuration. Review requested hardened Git reads and file-copy checks; final verification is recorded below.

Local administrator access, compromised Docker daemon, and concurrent hostile modification by the same OS user are outside a process-level sandbox guarantee. Static secret filtering cannot identify arbitrary credentials embedded in ordinary source text. No claim of complete dependency analysis or test-case-level regression inference is made.

## Windows acceptance (required before release)

1. Open installed and portable builds; confirm existing history, projects, profiles and settings remain available after restart.
2. At 100%, 125%, 150%, 175% DPI, inspect all five workspace tabs in Light, Dark, Purple Neon, Dark Fantasy and System themes; check keyboard focus, dialogs, Russian text and long Windows paths.
3. Intelligence: scan a repository containing ignored `.env`, tracked sensitive files and a symlink; verify excluded sources cannot be viewed. Add/search/edit/delete source-backed facts and decisions, restart and reopen them.
4. Architect: prepare/edit/save/reopen all 12 sections, approve and transfer to the existing team. Confirm editing invalidates approval. Explicitly authorize one ChatGPT/Codex refinement only when desired.
5. Budget: set one-call policy, run a small task, verify next agent does not start after the limit and checkpoint/reason are present. Raise policy and resume. Confirm missing SDK usage displays no invented tokens or account quota.
6. Git: checkpoint a dirty tracked file plus untracked file; compare two points; preview recovery; modify source after preview and verify stale recovery rejection. Recover using a new preview; verify source branch/index/files unchanged and restored worktree SHA matches.
7. QA: without Docker/local image verify BLOCKED, not PASS. Configure a trusted immutable local Linux image with installed tools; preview and confirm checks. Verify PASS/FAIL, missing tests → PARTIAL, timeout/cancel, baseline and PR report. Confirm no host dependency install or network pull occurs.
8. Complete existing run flow, Action Center denial/approval, pause/resume/stop, steering/queue, diff/artifacts/history and restart recovery.

Native Windows WebView2, actual DPI, installed/portable packaging and live Codex provider execution are **not verified in Linux**.

## Chromium verification

Command: `NODE_PATH=/tmp/codex-browser-tools/node_modules node tests/v2_browser.cjs`.

Result: **75 layout checks passed** (five screens × five theme preferences × 1024/1366/1920 px); no uncaught JavaScript errors, horizontal document overflow or unmapped fixture endpoints. Explicit HTTP contract fixtures test editing/saving a specification, diff view, QA log view, null initial Intelligence, null QA configuration/NOT RUN, offline error and retry. These are fixture tests, not live agent runs.

The first screenshot review found native unstyled buttons and oversized JSON budget output. The frontend was corrected to semantic button styles and compact role/run metrics with real budget thresholds; the complete matrix was rerun. Representative Light, Purple Neon and Git screenshots were inspected visually. Evidence lives outside Git at `/workspace/codex-v2-evidence`; `results.json` records assertions and mutations.

Command for real-backend mode: `LIVE_URL=http://127.0.0.1:8769 NODE_PATH=/tmp/codex-browser-tools/node_modules node tests/v2_browser.cjs` against an explicitly isolated temporary Git repository, real FastAPI services and FakeCodexProvider with live SDK connection hard-disabled. Successful scenarios include all five screens, index refresh/source read, create/save/approve specification, project budget save, checkpoint creation/comparison, restore preview, confirmed recovery into a new worktree, and configured QA preview/confirmation with unavailable local image producing BLOCKED. Real backend operations are not mocked; Codex execution is deliberately unavailable. See `live-results.json` for the final scenario list and `live-*.png` for screenshots.

## Bounded indexing measurement

A temporary repository with 1001 tracked text files was measured using `time.monotonic()` around `IntelligenceService.analyze`: cold **666.19 ms**, unchanged cached call **543.16 ms**, same persisted architecture record. These are one local Linux measurements, not universal performance promises. The cached path still enumerates/stat-checks tracked files to invalidate working-tree edits; it avoids rebuilding/storing the architecture snapshot, not all filesystem work.

Final focused Chromium regression: `FOCUSED_MODE=1 NODE_PATH=/tmp/codex-browser-tools/node_modules node tests/v2_browser.cjs` passed direct `/#suite` bootstrap and delayed mutation checks. The project selector and five feature tabs are disabled while a mutation is pending, and restored after both successful and failed responses. The real-FastAPI fixture workflow was rerun against a restarted backend with the final integration/lease changes; all recorded scenarios passed again. Temporary server was stopped after verification.
