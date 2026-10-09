# Desktop architecture

Launcher owns one hidden same-executable backend and Windows Job; backend owns SDK children. Health readiness проверяет instance identity, а не ChatGPT authentication. Private shutdown требует ownership token. SingleInstance и backend lease привязаны к actual data root.

Installed data: `%LOCALAPPDATA%\CodexTeam`; resources: installation `_internal`. Portable ZIP marker выбирает adjacent `data/`; installer marker не содержит. Explicit CODEX_TEAM_DATA_ROOT имеет приоритет.

WinForms работает на отдельном STA thread; services используют BeginInvoke. Tray poll использует plain desktop-state/settings endpoints, не SDK account probes. Notifications имеют bounded persisted dedupe; stage balloons default off. Active close проверяет health вне UI thread и предлагает tray/stop/cancel.

Native API: choose_project, open_logs, retry, exit, open_project(project_id), open_worktree(run_id), export_diagnostics, recovery_status, dismiss_recovery. Нет command/path-execution bridge. Navigation handlers заменяют unfiltered new-window opener; privileged page остаётся local root, безопасные user-activated HTTP(S) links уходят в system browser.

Session marker отмечает clean/abnormal shutdown; diagnostics содержит fixed redacted log tails и metadata, без DB/auth/project tree. Native source smoke report описывает фактический CLR/WebView2 test; final installed integration проверяется отдельно.
