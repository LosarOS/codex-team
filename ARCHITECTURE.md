# Архитектура

`desktop.py` запускает windowed pywebview/WebView2 и owned backend. `desktop_runtime.py` определяет resources/data paths, SingleInstance, Windows Job, hidden children и bounded startup/shutdown. `desktop_services.py` содержит STA-marshalled NotifyIcon/navigation, recovery marker, notification ledger и diagnostics allowlist. [Desktop details](DESKTOP_ARCHITECTURE.md).

FastAPI/SQLite обеспечивают loopback API, agents/packs/settings/history/events/actions. Engine проходит pipeline; каждую роль обслуживает отдельный официальный Codex thread с snapshot instructions. Provider adapter ограничивает finite RPC и отслеживает owned/inflight clients. API backend — явный custom provider того же SDK, без fallback.

WorkspaceManager создаёт isolated Git worktrees, baseline/diff/checkpoint и project memory. Runtime discovery добавляет точечные interpreter/stdlib grants. Strict structured results плюс current-turn execution ledger задают QA/review completion gates.

Один writer/run владеет data-root lease. Read-only specialists последовательные. Backend/SDK children принадлежат launcher; desktop stop не адресуется чужим процессам. Recovery сохраняет partial changes и повторяет только незавершённый stage. [Permissions](docs/PERMISSIONS.md).
