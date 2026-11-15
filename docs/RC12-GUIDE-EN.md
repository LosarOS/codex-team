# Codex Team RC12: plan, context and control

Final candidate guide after merging [PR18](https://github.com/LosarOS/codex-team/pull/18); published RC11 is the previous release.

**Evidence boundary:** canonical binary source `ccd0500e07c79eca7cbbea1e098f8c05d8e6a0f6`, [main Windows run43665690346](https://github.com/LosarOS/codex-team/actions/runs/43665690346): **1041 passed / 1 skipped**,1042 total,0 failures/errors. The last full Linux suite on final code: **1038 passed / 4 skipped**. Platforms and repeated checks are not summed. All 3 binary files were downloaded separately and checked for bytes/SHA256/CRC/PE/paths; [original evidence and candidate downloads](../reports/evidence/rc12-main-candidate/README.md).

Canonical native GUI verified the window, form, portable marker, actual backend-ready UI indicator, native picker, JSON write and graceful exit0 without forced cleanup or remaining owned processes. Source/probe exactly match main T. [GUI proof](../reports/evidence/rc12-main-candidate/native-gui-proof.json) · [Independent verification](../reports/evidence/rc12-main-candidate/independent-gui-evidence-verification.json). The written JSON body is not included in this archive; an old payload is not relabelled as new. This bounded automatic Windows acceptance is not full physical GUI/DPI/Narrator/live SDK acceptance. Release publication requires separate owner approval.

**Startup fix:** backend health is separate from Codex status. A neutral initial check becomes observed online/offline; SDK delay no longer causes a false red offline indicator. Unknown authorization keeps agent execution disabled, and login/API banners do not present unknown state as confirmed.

Task Architect now stores plans with up to 20 steps, acceptance criteria, relative files and named prerequisite selections. Cycles, missing dependencies and stale revisions are rejected. Shared files are warnings; root steps are not proven independent. Plans never execute themselves. A saved root step can explicitly populate the main composer after confirmation; standard access, isolation and no auto-commit are selected. Launch remains a separate action.

Project Knowledge shows source freshness. Matching hashes mean matching files, not independently verified claims. Stale, malformed and legacy unbound entries remain stored but are excluded from context until reviewed and saved again. Context preview is bounded to 512–12000 characters, performs no model call and labels repository content as untrusted data.

Mission Control uses actual saved events and distinguishes blockers and next actions without invented progress. Explicit starts, frozen budgets, independent worktrees and no automatic merge remain intact.

Budget export covers the selected page/project/UTC date, not the whole history or account quota. Unknown tokens/cost/quota remain null; task text, paths and raw usage are excluded. Desktop export uses a native Save dialog and a fresh backend snapshot with the same filters; browser export downloads the displayed JSON. Native cancellation/errors never fall back to an automatic browser download.

[Actual window, Budget preview and native Save captures](screenshots/rc12-main-candidate/README.md) came from disposable Windows Server, source/probe `ccd0500…`, canonical run43665690346. Login/model execution was not requested; normal GUI SDK discovery call count is unknown (`null`). Historical 6e/C0/6807 folders remain separate and do not replace current evidence.

Before upgrading, stop work explicitly, Quit and back up the whole data directory. Existing history, settings, projects and queue remain; restart must not resume missions automatically. Unsigned binaries and physical Windows/WebView2/live-account acceptance have separate evidence boundaries.
