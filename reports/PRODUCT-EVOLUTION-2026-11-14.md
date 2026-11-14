# Product Evolution — 2026-11-14

## Approved scope

User approved the proposed scope on2026-11-14. Target candidate: 1.0.0-rc12. Baseline HEAD: `0269b3db6b8d485b6880784f827c9719984aaabb`.

Mission Control event timeline; editable planning; source freshness/context preview; factual budget export. RU/EN, existing themes/data/consent preserved. Russian-primary README with full English alternative; real screenshots only.

## Environment and workflow

Managed Linux executor now available; GitHub CLI authenticated as LosarOS. Fresh clean clones, isolated feature branches. .NET10.0.404 installed in task-owned /workspace/.dotnet; Python3.12 virtualenv /workspace/.venv-codex. Six agents own disjoint sections with shared-file narrow edits coordinated. Root owns integration, review, Windows CI and artifacts.

No final publication approval yet: prepare artifacts and PRs, request separate confirmation before final release. Never merge protected main without required approval. Preserve existing releases.

## Current state

Implementation in progress. No new test/build/runtime PASS claimed until actual execution. Physical Windows/DPI/multi-monitor/live SDK remain distinct gates. Next: integrate modules, targeted checks, full regression, Windows candidate build and genuine evidence.
