# UI reliability and Mission Control validation

Baseline: `1d91d21` (`master`). No live model execution or paid API inference.

| Check | Actual outcome |
| --- | --- |
| Baseline `python -m pytest -q` | 389 passed, 9 failed, 3 skipped |
| Changed tree `python -m pytest -q` | 392 passed, 9 failed, 3 skipped |
| Failure-set comparison | Same exact nine test node IDs; no new failing test |
| Final UI/API/diagnostic subset | 59 passed (UI contracts, UI/server integration, server, desktop services) |
| JavaScript | `node --check` app.js and mission-control.js; projection and synthetic DOM scenarios pass |
| Real Chromium fixtures | See [browser validation](ui-browser-validation.md); separate from live/Windows acceptance |

The existing failures are in `tests/test_runtimes.py`: base Python executable,
node/dotnet/java/cargo availability, PowerShell command construction, and three
PowerShell unittest invocation cases. They reproduce on unmodified master in this
Linux environment (including missing `powershell`). Runtime behavior and tests
were not changed or skipped to manufacture a green suite. The existing
Starlette/httpx deprecation warning remains.

Regression scenarios cover held duplicate create/control submissions, stale
cross-run action responses, unchanged Action Center draft identity, six pipeline
modes, retries, planned repeated QA stages, partial event pagination, missing
timestamps, actual error filters and preserved results. New static helper is
served by FastAPI and included by existing wildcard package data. Existing
provider/permission/SDK contracts remain unchanged.

Screenshots before/after and results are generated outside Git. The browser
harness can regenerate them with clearly synthetic fixtures. Windows WebView2,
DPI, native folder picker, tray/notifications, final installer/portable lifecycle,
installed profile migration and live SDK approval remain unverified here. Use the
[Windows acceptance checklist](ui-ux-audit.md#existing-rc-risks-and-exact-windows-acceptance).
