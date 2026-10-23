# RC11 packaging and dependency review

Session: 2026-10-23. This document records checks actually performed and gates still pending; it is not a Windows runtime acceptance certificate.

## Dependency audit

`pip-audit --no-deps --disable-pip -r requirements-desktop.txt --format json` queried the advisory service for all **40 exact desktop pins**. Dependency resolution was intentionally disabled because this file already enumerates the Windows build environment and the audit host is Linux. This verifies the enumerated packages, not arbitrary unlisted transitive packages or native libraries.

Initial findings: **36 advisories in 2 packages**.

| Package | Previous pin | Advisory evidence | Fixed pin |
|---|---|---|---|
| certifi | 2026.7.22 | PYSEC-2026-4320 / GHSA-6q48-6c7w-9gw2; advisory recommends >=2026.10.19 | 2026.10.23 |
| Pillow | 12.3.0 | 35 advisories; fixes reported in 13.0.0 | 13.0.0 |

Pillow advisory IDs returned by the service: CVE-2026-112895, CVE-2026-112400, CVE-2026-112397, CVE-2026-112896, CVE-2026-112897, CVE-2026-112395, CVE-2026-112404, CVE-2026-112899, CVE-2026-112402, CVE-2026-112900, CVE-2026-112893, CVE-2026-112392, CVE-2026-112891, CVE-2026-112405, CVE-2026-112390, CVE-2026-112401, CVE-2026-112901, CVE-2026-112391, CVE-2026-112894, CVE-2026-112406, CVE-2026-112399, CVE-2026-112892, CVE-2026-112393, CVE-2026-112396, CVE-2026-96638, CVE-2026-96641, CVE-2026-96640, CVE-2026-96642, CVE-2026-96639, CVE-2026-96643, CVE-2026-96637, CVE-2026-96644, CVE-2026-96778, CVE-2026-96636, GHSA-78g4-xqwv-q3g8.

No exploit against Codex Team was reproduced. Source search found Pillow usage in the build-time icon generator; no production image-upload decoder was found. The bundle is rebuilt with the fixed package anyway. The certificate-store advisory affects a shared trust dependency and is addressed directly.

After changing the pins, the same audit reported **no known vulnerabilities in 40 packages**. This is a dated advisory lookup, not a claim that the product has no vulnerabilities. An isolated Pillow 13.0.0 check generated and decoded the icon at 16/24/32/48/64/128/256 pixels and the 256-pixel PNG successfully. No tracked image was overwritten by that check. PyPI supplied the Python 3.12 Windows x64 Pillow wheel (7,272,166 bytes) and universal certifi wheel (135,082 bytes); actual bundled execution remains a native CI gate.

## Installer and publication boundaries

The installed smoke now refuses execution outside a disposable GitHub Actions runner and refuses an existing per-user installation registration. A unique `/DIR` alone would not isolate Inno Setup's shared AppId and shortcuts.

The native smoke adds these required assertions:

- Actual installed Project Doctor and queue preflight endpoints remain read-only and do not claim provider/GUI validation.
- Reinstalling the same version over itself preserves an exact hash listing of the isolated profile before backend restart.
- History, queue, language/theme and local notes survive the restart.
- Uninstall preserves profile bytes and removes the test executable and registration.
- Reinstallation starts the real frozen backend with the preserved profile and does not auto-dispatch pending work.

This is a **same-version repair/upgrade test**, not a claim that every earlier-version migration was exercised. Only test-owned temporary data is inspected; the owner's profile is not opened or removed.

Both release workflows keep uploads as a draft until they re-download the GitHub binary assets, match the uploaded checksum manifest, verify every SHA256 and check nonzero file sizes. They do not replace existing releases or assets. Publication rejects a skipped source suite, and the artifact-only publishing workflow requires the expanded RC11 native smoke gates. Its validation script was executed against synthetic contract fixtures: missing/false gates and skipped-suite evidence were rejected, while complete evidence passed.

## Executed checks and pending gates

- Linux static packaging/workflow/archive contract suite: **17 passed**.
- Dependency advisory lookup and Pillow generation: passed as described above.
- Initial native candidate: [Windows run 39951850503](https://github.com/LosarOS/codex-team/actions/runs/39951850503), source `1364c38`; in progress at this checkpoint, and predates these hardening changes.
- Native builds now retain full-suite JUnit evidence and stage `source-test-results.json` with exact passed/skipped counts, duration and source commit. Build failures preserve JUnit diagnostics; pytest exit checks remain mandatory.
- Final native packaging, new installed smoke, published-asset verification: **pending** on the final source commit.
- Interactive WebView2, real Windows DPI, physical-PC user acceptance and code signing: **not verified** here. Binaries remain unsigned.
