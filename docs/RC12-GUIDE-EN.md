# Codex Team RC12: plan, context and control

Candidate guide for [PR18](https://github.com/LosarOS/codex-team/pull/18); published RC11 is the previous release.

**Evidence boundary:** binary source `6e00643676dd9b2e701fdccf50fa8b75ff59fd00` has **985 passed / 1 skipped** on Windows (986 total), **982 passed / 4 skipped** on Linux. These are two environments of the suite, not additional unique tests to sum together. Candidate bytes were verified separately. Native budget Save is **IMPLEMENTED / NOT RUNTIME VERIFIED**: opening the picker does not prove JSON was written. Final gates and owner approval remain required before publication.

Task Architect now stores plans with up to20 steps, acceptance criteria, relative files and named prerequisite selections. Cycles, missing dependencies and stale revisions are rejected. Shared files are warnings; root steps are not proven independent. Plans never execute themselves. A saved root step can explicitly populate the main composer after confirmation; standard access, isolation and no auto-commit are selected. Launch remains a separate action.

Project Knowledge shows source freshness. Matching hashes mean matching files, not independently verified claims. Stale, malformed and legacy unbound entries remain stored but are excluded from context until reviewed and saved again. Context preview is bounded to512–12000characters, performs no model call and labels repository content as untrusted data.

Mission Control uses actual saved events and distinguishes blockers and next actions without invented progress. Explicit starts, frozen budgets, independent worktrees and no automatic merge remain intact.

Budget export covers the selected page/project/UTCdate, not the whole history or account quota. Unknown tokens/cost/quota remain null; task text, paths and raw usage are excluded. Desktop export uses a native Save dialog and a fresh backend snapshot with the same filters; browser export downloads the displayed JSON. Native cancellation/errors never fall back to an automatic browser download.

Before upgrading, stop work explicitly, Quit and back up the whole data directory. Existing history, settings, projects and queue remain; restart must not resume missions automatically. Unsigned binaries and physical Windows/WebView2/live-account acceptance have separate evidence boundaries.
