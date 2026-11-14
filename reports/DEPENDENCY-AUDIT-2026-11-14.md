# Codex Team — exact desktop pin advisory audit

2026-11-14. Tool: **pip-audit2.10.1**, PyPI advisory service. This audit queried package names and exact versions only; no user projects, task text, secrets or source files were uploaded. No Windows dependency installation was performed by the audit.

## Method and coverage

```text
/workspace/.venv-audit/bin/pip-audit --disable-pip --no-deps -r requirements-desktop.txt --progress-spinner off --format json
```

**40 exact declared desktop/build pins covered**, zero skipped/unknown records. `--disable-pip --no-deps` avoids executing pip resolution or installing Windows packages on Linux; it audits exactly the declared inventory. The file includes SDK/CLI binary distribution pins and packaging tools as Python distributions, but this is **not an inspection of embedded native/Node dependency trees**.

Before remediation: exit1, **two known advisory records in two packages**. After the two approved patch updates: exit0, **zero known findings** for all40 pins, zero skips. The warning recommending hash-locked requirements is retained as a reproducibility limitation; exact version pins are not supply-chain authenticity proof.

## Confirmed findings and minimal fixes

| Package before | Advisory | Severity | First patched / selected |
| --- | --- | --- | --- |
| opentelemetry-api1.45.1 | [GHSA-mf5v-w3w3-f6cg / CVE-2026-126360](https://github.com/advisories/GHSA-mf5v-w3w3-f6cg) | Medium | 1.45.2 |
| setuptools84.0.0 | [GHSA-xmj3-9gf7-h52w](https://github.com/advisories/GHSA-xmj3-9gf7-h52w) | Low | 84.1.0 |

OpenTelemetry: regex denial of service requires attacker-controlled traceparent data reaching the affected propagator through a carrier that preserves embedded newlines and accepts sufficiently large values. It is not evidence that this application exposes an exploitable endpoint; no exploit was executed. The patch limits input and fixes the regex behavior.

Setuptools: Windows legacy `Wheel.install_as_egg` namespace metadata can direct a fixed-content `__init__.py` write outside the intended destination. This concerns installation/build processing of attacker-controlled wheel metadata, not demonstrated arbitrary code execution by Codex Team. No malicious wheel was run. Both fixes were approved by root; only exact patch pins in requirements-desktop.txt changed, no major upgrades or application permission changes.

## Evidence

- [Before](evidence/evolution-2026-11-14/desktop-pins-before.json)
- [After](evidence/evolution-2026-11-14/desktop-pins-after.json)
- [Manifest and requirement SHA256](evidence/evolution-2026-11-14/desktop-pin-audit-manifest.json)
- [OpenTelemetry advisory metadata](evidence/evolution-2026-11-14/opentelemetry-advisory.json)
- [Setuptools advisory metadata](evidence/evolution-2026-11-14/setuptools-advisory.json)

GitHub primary advisory API metadata independently confirmed both first-patched versions and affected ranges. Source hygiene/packaging checks: `pytest tests/test_windows_release_workflow.py tests/test_publish_windows_artifact.py -q` **32 passed**,0.63s; this is a targeted subset, not an extra full-suite total.

## Other tooling / exclusions

Root's earlier environment audit found known pip25.0.1 advisories in the Linux development environment; root updated that tool to26.3. Pip is not a pin in requirements-desktop.txt. Do not mix environment-tool findings with the40-package release inventory.

Not covered: Windows OS/WebView2, bundled Git, Python runtime native libraries, actual frozen bundle composition, embedded SDK/CLI dependency graphs, package provenance/signatures, zero-days, exploitation/reachability of every dependency, or physical Windows runtime. A clean advisory lookup is not exhaustive security certification.

After root confirmed its full suite completed, shared development venv was updated: opentelemetry-api1.45.2 was already present; setuptools84.1.0 installed successfully. No other dependencies changed. Targeted packaging/provider verification after installation: **98 passed**,0.99s; `pip check` reports no broken requirements. A fresh40-pin audit remains clean. These98tests overlap the earlier32 and are not summed as extra unique coverage. Final Windows build and regression must use the patched requirements and source commit; previous candidate artifacts cannot prove these new pin bytes.
