# RC security review

Scope: local source review and targeted regression tests of the desktop bridge, loopback API, SDK permission configuration, runtime discovery, Action Center, checkpoint handling, project memory and credentials. This is not an external penetration test or a certification. Public evidence excludes personal paths, credentials and raw model transcripts.

## High-priority findings corrected

| Finding | Correction and evidence |
| --- | --- |
| Shell/Git installation grants or shared Git metadata could expand to a home directory or filesystem root. | Broad tool parents receive no directory grant; only the exact executable can be granted there. Shared Git metadata remains readable at its exact path, while a broad parent receives neither a directory grant nor workspace-root status and is excluded from runtime discovery. Three focused root/home regressions pass. Runtime libraries use specific validated paths. |
| Unknown nested permission fields could be presented as understood, approvable scope. | Strict official wire-shape validation rejects unknown fields, malformed types, ambiguous relative paths and broad/credential scope. Unsupported requests are persisted and declined. The four original audit regressions now pass. |
| QA success could rely on a claimed result without a successful native test execution. | QA requires current-turn native execution evidence and positive nonzero test counts; native test failures also block success. Process wrappers must launch the same Python process, wait for it and propagate its real exit code. Printed runner source, mismatched processes, empty suites and masked failures are rejected. |
| Stage edits made before a user-decision result were not reliably checkpointed for resume. | Returned permitted stage edits are captured before verdict/evidence errors. Interrupted partial edits require completed native file-change provenance and exact content hashes. External content or HEAD changes do not advance the checkpoint. Native-owned resume and external text/binary tamper regressions pass. |
| Earlier project memory could be reused after workspace or code changes. | Memory requires matching authoritative workspace, analyst snapshot HEAD, diff hash and summary-content hash. Legacy, altered and stale summaries are omitted. Model reports remain explicitly untrusted evidence. |

## Boundaries verified in source and focused tests

- The server binds to loopback and rejects foreign Host/Origin, cross-site mutation requests and mutation content types other than JSON. Responses include CSP and no-sniff headers.
- The desktop bridge exposes fixed actions, validates local page trust and resolves registered project/worktree identifiers. It exposes no general shell or arbitrary host-command endpoint.
- Registered commands remain argv data for native Codex execution under the role's policy. Runtime preflight executes no repository scripts, installers or interpreters and silently grants no network/write access.
- Developer is the only pipeline writer. Network defaults off; an explicitly enabled Developer capability still requires the real native approval flow. Read-only core roles cannot acquire write or network grants.
- Provider selection is explicit and recorded at run creation. There is no automatic provider or billing fallback. API credentials use Windows Credential Manager; production has no plaintext storage fallback. API shell-environment exclusion is configured.
- Native action grants require a live request; stale approvals cannot be replayed. Product Resume/Explain/Stop cards grant no SDK permissions. Explicit total-budget changes are bounded.
- Worktree deletion uses an exact inactive run path and native Git removal without force. Dirty worktrees, links/junctions, pending decisions and forged targets are refused; history is retained.

## Remaining limits

- Native Codex sandbox and approval enforcement are the execution boundary. Application command classification does not intercept native tools. Git hooks/filters are disabled or refused for application-owned Git operations; native SDK Git operations remain subject to its own policy.
- Code/diff views display source as text and do not establish its safety. Project tests and scripts can execute arbitrary repository code when authorized through native tools.
- This is a single-user desktop product. Loopback/CSRF controls and Credential Manager do not protect against malware or other programs already running as the same Windows user.
- Tool detection checks bounded files and installation layouts, not executable signatures or a dependency vulnerability database. Missing tools/packages require user setup; preflight performs no installation.
- Unsupported broad/glob permission requests are declined. Complex interrupted edits without verifiable native file-change provenance remain preserved for review rather than being silently accepted.
- Reasoning is excluded and common secret forms are redacted, but redaction is not a comprehensive data-loss-prevention guarantee. Diagnostic exports should be reviewed before sharing.

The final full-suite and frozen desktop results belong in the release manifest; they are not inferred from this focused review. No paid API model calls or external attack campaign were performed for this report.
