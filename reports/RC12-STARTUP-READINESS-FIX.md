# RC12 — local backend readiness vs account discovery

2026-11-15. Confirmed from actual canonical Windows screenshot and source: initialization called renderStatus while online=false before any health response, showing false-red backend-unavailable. A healthy backend could also be labelled offline when SDK-dependent /api/status exceeded the12-second GET timeout.

## Fix

- Initial HTML and first render show localized neutral checking, never a fabricated transport error.
- Existing cheap read-only /health settles local transport immediately and independently of SDK account discovery; health errors do not become fake online.
- Latest health probe wins; late success or failure cannot overwrite newer readiness.
- Provider discovery remains separate: pending/unverified indications and error details; no login-required/API-key-required banner until a settled known result.
- Unknown/pending provider state keeps Start/Resume/login guarded. After transport recovery a fresh provider result is required before enabling execution; permissions, billing consent and all launch actions are unchanged.
- Existing serialized refresh/poll/selection guards retained. No new model/login/provider-test call or background scheduler. Health GET uses a bounded5-second timeout; transport errors on another endpoint are checked against actual health rather than inferred from SDK latency.
- Accessible status label/live region plus data-connection-state=checking|online|offline. Identical badge contents are retained across polling to avoid repeated live-region subtree replacement; this is not a claim of full Narrator acceptance.

## Actual source-side evidence

26 relevant Python/UI contract cases passed in1.78s, including8 new readiness regressions: real app.js DOM initial checking, SDK HTTP failure with healthy backend, failed backend despite successful auth, deferred SDK response, known authentication required, identical aria-live subtree retention, conservative auth gating after transport recovery, and deferred overlapping health responses in both orders. No POST or model/provider call was introduced in these scenarios. Existing 15 Node scripts and the new backend_readiness script all passed (16scripts). Source parse and diff checks passed.

The previous canonical native screenshot/report is preserved as historical evidence. The fixed frontend still requires fresh full regression and actual Windows GUI acceptance for its exact source commit; no prior GUI proof is relabelled as testing this change. Physical Windows10/11, Narrator/DPI and live SDK development remain separate gates.

## Actual Windows acceptance

The source6807 native pipeline and independent read-only review passed. UI Automation waited for an actual visible healthy backend label before capture; the unchanged screenshot shows «Сервер доступен · проверяем Codex…». Native Save wrote the JSON and Quit returned0 without force cleanup. [Original before/after and exact evidence](evidence/rc12-startup-fixed-checkpoint/README.md).1041passed/1skipped source cases on Windows; SDK account calls remainunknown, physical/DPI/live model mission are separate. Subsequent merge-source packaging is validated independently before publication.
