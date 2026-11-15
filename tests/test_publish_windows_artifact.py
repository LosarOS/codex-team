"""Release-only workflow never rebuilds or executes downloaded user code."""
from pathlib import Path
import ast
import textwrap
import json
import pytest

EVOLUTION_GATES = (
    "evolution_budget_export_verified", "evolution_plan_verified",
    "evolution_context_preview_verified", "evolution_no_dispatch_verified",
    "evolution_plan_restart_verified",
)
NATIVE_GATES = (
    "start_menu_shortcut_verified", "project_doctor_verified", "queue_preflight_verified", "same_version_upgrade_verified",
    "uninstall_data_preservation_verified", "reinstall_restart_verified",
    "mission_queue_restart_verified", "appearance_restart_verified", "notebook_restart_verified",
)


def test_release_only_workflow_guards_and_python_validation():
    workflow = Path('.github/workflows/publish-windows-artifact.yml').read_text()
    for required in (
        "run['path'] == '.github/workflows/windows-release.yml'",
        "run['event'] == 'push'", "run['conclusion'] == 'success'",
        "run['head_repository']['full_name']", "run['repository']['full_name']",
        'actions: read', 'contents: write', 'run-id: ${{ inputs.run_id }}',
        'github-token: ${{ github.token }}', 'hashlib.file_digest',
        "smoke['installed_backend_verified'] is True", "smoke['uninstall_verified'] is True",
        "smoke['model_calls'] == 0", "smoke['sdk_account_calls'] == 0",
        "tag == os.environ['RELEASE_TAG']", 'test "$tagged" = "$SOURCE_COMMIT"',
        'refusing to replace assets', '--target "$SOURCE_COMMIT"',
    ):
        assert required in workflow
    assert 'actions/checkout@' not in workflow
    assert 'build-desktop.ps1' not in workflow
    assert '--clobber' not in workflow
    assert '530' not in workflow
    scripts = workflow.split("python3 - <<'PY'\n")[1:]
    assert len(scripts) == 2
    for script in scripts:
        ast.parse(textwrap.dedent(script.split('\n          PY', 1)[0]))


def _release_validation_script():
    workflow = Path('.github/workflows/publish-windows-artifact.yml').read_text()
    return textwrap.dedent(workflow.split("python3 - <<'PY'\n")[2].split('\n          PY', 1)[0])


def _valid_artifact_fixture(tmp_path, monkeypatch):
    import hashlib

    script = compile(_release_validation_script(), '<artifact-validation>', 'exec')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SOURCE_COMMIT', 'a' * 40)
    monkeypatch.setenv('RELEASE_TAG', 'v1.0.0-rc12')
    root = tmp_path / 'release-assets'
    root.mkdir()
    checks = {}
    for name in ('CodexTeam-Setup-x64.exe', 'CodexTeam-Setup-x64.zip', 'CodexTeam-Portable-x64.zip'):
        data = ('synthetic contract fixture: ' + name).encode()
        (root / name).write_bytes(data)
        checks[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    (root / 'release-checksums.json').write_text(json.dumps(checks))
    (root / 'SHA256SUMS.txt').write_text(''.join(f"{entry['sha256']}  {name}\n" for name, entry in checks.items()))
    (root / 'build-verification.json').write_text(json.dumps({'app_version': '1.0.0rc12', 'sensitive_paths_found': 0, 'required_files_checked': 30}))
    (root / 'BUILD-NOTES.txt').write_text('Source commit: ' + 'a' * 40 + '\nFull source suite: passed.')
    (root / 'RELEASE-NOTES-RU.md').write_text('Synthetic release validation fixture')
    smoke = {'platform': 'Windows', 'installed_backend_verified': True, 'uninstall_verified': True,
             'model_calls': 0, 'sdk_account_calls': 0, 'installed_git_version': 'git version fixture', 'runtime_version': '1.0.0-rc12'}
    portable = {'platform': 'Windows', 'source_commit': 'a' * 40, 'model_calls': 0, 'sdk_account_calls': 0, 'runtime_version': '1.0.0-rc12'}
    smoke.update({gate: True for gate in (*NATIVE_GATES, *EVOLUTION_GATES)})
    portable.update({gate: True for gate in EVOLUTION_GATES})
    portable.update({gate: True for gate in ('archive_crc_verified', 'startup_verified', 'restart_verified', 'settings_history_queue_preserved', 'portable_backend_verified')})
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    path = root / 'installed-smoke.json'
    path.write_text(json.dumps(smoke))
    gui = {'status': 'OBSERVED_NATIVE_GUI_SCENARIOS_PASSED', 'source_commit': 'a'*40, 'probe_commit': 'a'*40,
           'owned_process_force_cleanup': False, 'owned_gui_backend_processes_remaining': 0,
           'login_requested': False, 'model_execution_requested': False, 'sdk_account_calls': None, 'backend_connection_observed_label': 'Сервер доступен · Codex не проверен'}
    gui.update({gate: True for gate in ('window_verified','task_form_verified','backend_connection_verified','portable_marker_profile_verified','budget_picker_verified','budget_saved_verified','graceful_quit_verified')})
    (root / 'native-gui-proof.json').write_text(json.dumps(gui))
    import zipfile
    with zipfile.ZipFile(root / 'CodexTeam-Native-GUI-Evidence.zip', 'w') as archive:
        archive.writestr('native-gui-proof.json', json.dumps(gui))
        for name in ('native-dashboard-task-form.png','native-budget-preview.png','native-budget-save-picker.png'):
            archive.writestr(name, b'\x89PNG\r\n\x1a\n' + b'synthetic contract fixture, not runtime evidence')
    return script, root, smoke, portable


def test_release_validation_rejects_missing_native_gates(tmp_path, monkeypatch):
    script, root, smoke, portable = _valid_artifact_fixture(tmp_path, monkeypatch)
    path = root / "installed-smoke.json"
    for gate in NATIVE_GATES:
        del smoke[gate]
    path.write_text(json.dumps(smoke))
    with pytest.raises(AssertionError, match='Missing native release gate'):
        exec(script, {})
    gates = NATIVE_GATES
    smoke.update({gate: True for gate in gates})
    path.write_text(json.dumps(smoke))
    exec(script, {})
    for gate in gates:
        smoke[gate] = False
        path.write_text(json.dumps(smoke))
        with pytest.raises(AssertionError, match='Missing native release gate: ' + gate):
            exec(script, {})
        smoke[gate] = True
    path.write_text(json.dumps(smoke))
    portable['runtime_version'] = '1.0.0-rc10'
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    with pytest.raises(AssertionError):
        exec(script, {})
    portable['runtime_version'] = '1.0.0-rc12'
    portable['portable_backend_verified'] = False
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    with pytest.raises(AssertionError, match='Missing portable release gate'):
        exec(script, {})
    portable['portable_backend_verified'] = True
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    (root / 'BUILD-NOTES.txt').write_text('Source commit: ' + 'a' * 40 + '\nFull source suite: skipped by explicit manual request.')
    with pytest.raises(AssertionError):
        exec(script, {})


@pytest.mark.parametrize("filename", ["installed-smoke.json", "portable-smoke.json"])
@pytest.mark.parametrize("gate", EVOLUTION_GATES)
@pytest.mark.parametrize("value", [None, False])
def test_release_validation_requires_each_rc12_gate(tmp_path, monkeypatch, filename, gate, value):
    script, root, smoke, portable = _valid_artifact_fixture(tmp_path, monkeypatch)
    # Establish a complete positive fixture before removing one proof only.
    exec(script, {})
    proof = smoke if filename == "installed-smoke.json" else portable
    if value is None:
        del proof[gate]
    else:
        proof[gate] = value
    (root / filename).write_text(json.dumps(proof))
    with pytest.raises(AssertionError, match="Missing RC12 frozen backend gate: " + gate):
        exec(script, {})
