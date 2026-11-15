# RC12 native GUI evidence — 2026-11-15

Status: **OBSERVED_NATIVE_GUI_SCENARIOS_PASSED**, not full physical Windows acceptance and not a published release.

[Actual run43659404286](https://github.com/LosarOS/codex-team/actions/runs/43659404286), candidate binary source6e00643676dd9b2e701fdccf50fa8b75ff59fd00, probe8c551c08fd8369ba47442a2627cbb0bb8b63b3cb. MCP artifact14139312183 actually downloaded and inspected; ZIP digest and original file hashes are in provenance.json.

Unchanged proof JSON verifies real window/task form, owned portable marker selection, actual Windows Save dialog, actual saved budget JSON and graceful GUI exit0. Remaining owned GUI/backend processes0; force cleanup false. Synthetic empty exported selection deliberately retains null measured tokens/quota/cost and usage_complete=false. No task text, private paths, credentials or API secrets occur in these JSON files.

[Four genuine PNGs](../../../docs/screenshots/rc12-native-gui/README.md) were visually reviewed; no open system error. The initial dashboard is captured while account discovery is still connecting; the task form is accessible below fold, not visually pictured. The Save path is a disposable runner fixture path; images are not retouched.

Earlier failed probes remain failed: managed exit-code handle issue, wrong modern dialog control types, absent managed LegacyIAccessiblePattern and programmatic filename input that did not produce the exact chosen output. Final probe uses verified filename HWND/class/ID/owner, foreground/focus-guarded normal keyboard input, exact text readback, one Save action, actual JSON validation and supported native window close. No application gate was waived and no app mutation/rebuild was needed for these probe corrections.

These proofs bind the stated existing candidate bytes. They do not imply that a later source commit was tested or permit publication before final canonical gates/owner confirmation. Physical Windows10/11, DPI/accessibility, live SDK work, long soak and full installed GUI matrix remain unverified. Startup account calls are unknown/null; no login or model action was requested.
