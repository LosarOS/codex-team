# Chromium fixture validation — 2026-10-15

This is real Chromium rendering with an isolated local HTTP fixture server. All run, account, permission, command, and usage data are explicitly synthetic. No Codex execution, provider request, or paid API call occurs. This is **not Windows Desktop E2E**.

## Reproduction

Chromium executable: `/usr/bin/chromium`. Playwright was installed outside the repository in `/tmp/codex-browser-tools`; it adds no production dependency.

```bash
NODE_PATH=/tmp/codex-browser-tools/node_modules node tests/browser_qa.cjs after
```

For the baseline, export `master:codex_team/static/{index.html,style.css,app.js}` into an isolated directory and set `UI_DIR` to that directory; run with argument `before`. The same fixture contract and layout checks were used for both revisions. The baseline predates Mission Control, so inspector/filter assertions apply only to the changed UI.

## Results

- Baseline and changed UI: 54 page/viewport checks (all nine navigation sections at 1024×768, 1280×720, 1366×768, 1440×900, 1920×1080, 2560×1440). No document horizontal overflow and no uncaught page errors.
- Three additional checks reduce the effective CSS viewport to approximate browser zoom at 125%, 150%, 175%. No document horizontal overflow. This is not a Windows DPI test.
- Startup issued no mutations. Pause and resume used `/api/runs/fixture_run/control` with the corresponding action. Deny used the existing action resolver, without an unsupported grant or new permission mechanism.
- Mission Control shortcuts: «Направить» focuses the existing instruction input; «Логи» opens the existing activity panel. The current activity row displays the actual fixture command event.
- Changed UI: selecting a pipeline attempt opens its agent inspector with iteration and duration; the command filter contains exactly one fixture command row with `git status`. Screenshots include the live-event fixture timeline.
- Synthetic FAILED, USER_DECISION_REQUIRED, PAUSED, AUTH_REQUIRED, USAGE_LIMIT, COMPLETED states rendered without uncaught errors. A 503 status response showed the offline banner; successful refresh removed it.
- First-login/empty/partial status fixtures show the authorization banner and disable task creation. Delayed event responses and a transient 503 are exercised through retry without provider access.
- Themes exercised through the actual settings select: light, dark, purple-neon, dark-fantasy, system.
- Partial event paging (`has_more=true`) preserves the persisted QA result in its selectable inspector while complete timing history is unavailable; browser regression asserts the saved QA summary.
- Computed sRGB contrast for `--text`, `--muted`, `--red`, `--yellow`, `--green` against `--panel`: all 25 theme/token checks exceed 4.5:1 (minimum 6.48:1, light warning; system resolved to light in Chromium). This covers these token pairs, not every composited UI state.
- Full-page screenshots reviewed for Dashboard, Runs/Mission Control, Action Center, and Settings. The checked long Windows path wraps inside the run and permission card. Purple Neon, Dark Fantasy, and Light retain visible control borders and text. This visual review is not a complete automated WCAG audit.

## UI changes from this review

Mission Control now follows the supplied execution-flow concept: circular factual status indicators, linked sequential cards, a compact current-agent/last-activity row, and functional steering/log shortcuts alongside the canonical pause/resume/stop controls. Reduced motion disables the current-stage spinner. It has semantic-token card backgrounds, a clearly selected attempt, visible keyboard focus, compact timing metadata, and responsive filter/heading layouts. Inputs keep an explicit focus outline; confirmation dialogs have a bounded height and vertical scroll for reduced effective viewports. Existing theme variables are preserved.

Baseline checks did not reproduce a page-level horizontal overflow, so this report does not claim to fix one. Pipeline horizontal scrolling is intentional and local to the pipeline.

## Evidence artifacts

Artifacts are generated outside Git to avoid committing binary screenshots:

- `/workspace/codex-team-browser-before/`: baseline Dashboard, Runs, Actions, Settings and theme screenshots; `results.json`.
- `/workspace/codex-team-browser-after/`: corresponding changed UI, Mission Control, command timeline, state fixtures, effective zoom captures, offline screenshot; `results.json`.

## Windows acceptance still required

1. Run the installed and portable builds under native WebView2 at 100/125/150/175% OS scaling. Verify all nine navigation sections and dialog scrolling at 1024×768 and 1280×720.
2. Check keyboard Tab, pipeline selection, Escape on dialogs, and focus visibility in every theme, including custom accent colors.
3. With an actual official Codex login, execute a small task; check stage transitions, command events, role retries, pause/resume, queued instructions, and terminal results.
4. Trigger an actual action request and confirm deny/allowed decisions through the existing backend restrictions; repeat after disconnect/reconnect.
5. Restart the installed build, confirm its displayed data directory, and verify existing history and worktree paths survive.

Actual model execution, native folder picker, tray/lifecycle integration, package installation, installed-profile migration, and native Windows scaling were not tested here.
