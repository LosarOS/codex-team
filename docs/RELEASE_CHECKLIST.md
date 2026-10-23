# RC11 release checklist

Use [the current engineering report](../reports/engineering-session-2026-10-23.md) and the published release evidence for actual outcomes. Earlier RC1/V2 reports describe older binaries. This checklist does not turn an unexecuted gate into PASS.

## Automated publication gates

- Final successful Windows push build binds the artifact to its exact source commit. Full Python suite is enabled; JUnit counts and source SHA are retained in `source-test-results.json`.
- `build-verification.json` checks bundled files, official CLI and executable imports; no sensitive profile paths are bundled.
- Actual extracted portable archive passes entry-boundary/CRC checks, backend start/restart and isolated settings/history/pending-queue preservation with no model calls.
- Actual installer passes per-user installation, Unicode Start Menu target/directory, backend assets/Doctor/preflight, same-version repair, uninstall/profile preservation, reinstall/restart and no automatic mission dispatch. Run only on a disposable CI runner; refuse existing installations and shortcuts.
- `CodexTeam-Setup-x64.exe`, `CodexTeam-Setup-x64.zip` and `CodexTeam-Portable-x64.zip` have nonzero sizes matching `release-checksums.json` and `SHA256SUMS.txt`.
- Publication creates a draft, downloads the GitHub assets, checks their actual SHA256 and only then publishes the prerelease. Never replace assets or retag an existing release to another commit. Diagnostic builds with skipped suites cannot be published.
- Release notes disclose unsigned binaries and all unverified gates. Windows target support is distinct from tested Windows runner versions.

## Interactive acceptance before stable 1.0

Use a fresh disposable Windows account or VM and back up any existing data before an upgrade. Do not run destructive CI smoke on an owner's profile.

1. On Windows 10/11 x64, install and open the actual desktop window through its shortcut. Confirm WebView2 renders, no unexpected console appears, and normal close/reopen releases owned processes.
2. Authenticate through official ChatGPT/Codex login. Add a small clean committed Git project, inspect Project Doctor and verify separate unknown build/runtime gates. Run no recommended command without reviewing its permissions.
3. Configure Standard with ordinary workspace access, isolation and a bounded budget. Run one harmless independently verifiable task; inspect planning, developer changes, tests, QA/review, final diff and recorded usage. Unavailable metrics stay unknown.
4. Add independent pending missions, reorder, inspect preflight and explicitly confirm. Check authentication/usage/decision/failure/interruption blocks. Inspect unknown outcomes before retry; pause after current, close/reopen and verify no automatic restart or merge.
5. Check RU/EN, the theme matrix, Tab/Enter/Escape, focus restoration, screen reader, high contrast, large text and 100/125/150/200% DPI. Narrow windows must retain reachable actions and readable diagnostics.
6. For portable, extract into a writable Unicode path and launch through its normal GUI. Confirm `portable.json` chooses the adjacent `data` directory and installed data is unaffected. Backend-child smoke with an explicit data root does not prove this GUI path.
7. Back up and test a supported earlier-version upgrade separately from same-version repair. Preserve history, projects, queue, drafts, settings, worktrees and authentication. Verify updater behavior, uninstall and reinstall without deleting the data profile.

Record Windows build, exact release/source SHA, evidence, failures and remaining limits. Until these interactive gates pass, publish only a prerelease with disclosed limitations; do not label the product a verified stable release.
