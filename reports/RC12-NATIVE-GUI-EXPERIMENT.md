# Actual Windows WebView2 GUI experiment — prepared protocol

Status: **NOT VERIFIED** until a successful Windows run and inspection of actual artifacts. This standalone experiment does not publish, rebuild or replace a release and is not yet a release gate.

## Invocation

After a successful candidate run with exact source SHA, root can create isolated branch `ops/native-gui-experiment` from the reviewed feature head and commit only `.github/gui-experiment-request.json` containing exactly `run_id` and `source_sha`. Only that branch/path combination triggers the push experiment; normal feature/master pushes do not. This allows validation without merging an unapproved feature into the protected branch. Alternatively dispatch `.github/workflows/native-gui-experiment.yml` using `run_id` and `source_sha`. It accepts only a successful same-repository `.github/workflows/windows-release.yml` run, downloads its `codex-team-windows-x64` artifact, verifies the actual portable ZIP size/hash against its manifest and checks backend/source proof before launching anything.

`packaging/Smoke-DesktopGui.ps1` uses **Windows PowerShell5.1 STA + Windows UI Automation** and the actual extracted portable EXE. The script refuses non-Windows/non-GHA and existing CodexTeam processes. All resources/data/exports live in a newly allocated RUNNER_TEMP directory. It does not touch an installed owner profile, uninstall anything, delete original user data or install software.

## Actual observations attempted

1. Seed an owned ready project through the real frozen backend without executing a run; shut it down.
2. Launch actual GUI EXE without data override so portable.json must choose its owned data directory. Empty dedicated CODEX_HOME prevents use of owner credentials.
3. Find the actual owned native window and accessible task form; save screenshot.
4. Navigate Budget, preview current-page export, open actual native Save dialog, save JSON inside owned directory; validate report and capture genuine screenshots.
5. On failure, retain real failure screenshot, bounded UIA control names, logs and JSON partial results. Never substitute browser fixtures or generated images.

The page is not injected or driven through undocumented browser access. `--force-renderer-accessibility` is a normal renderer accessibility argument used for UIA exposure. Screenshots are unretouched.

## Explicit limits

Normal app startup requests provider/account discovery through `/api/status`. No login, model invocation or task-start action is requested, but SDK account-call count is **unknown/null**, not zero. The experiment is disposable Windows Server, not physical Windows11/DPI/Narrator acceptance. Cleanup force-terminates only processes whose executable is the unique extracted EXE; graceful quit is **not verified** and is disclosed in proof. Resources remain in disposable runner temp rather than deleting an owner directory.

PowerShell/UIA execution and native picker controls must be confirmed from actual run artifacts. An unexposed/missing accessible control is an experiment failure, not evidence that native UI works. Source-side browser and backend tests cannot close this gate.
