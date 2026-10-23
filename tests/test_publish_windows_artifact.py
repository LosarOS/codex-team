"""Release-only workflow never rebuilds or executes downloaded user code."""
from pathlib import Path
import ast
import textwrap


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


def test_release_validation_rejects_missing_native_gates(tmp_path, monkeypatch):
    import hashlib
    import json
    import pytest

    script = compile(_release_validation_script(), '<artifact-validation>', 'exec')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('SOURCE_COMMIT', 'a' * 40)
    monkeypatch.setenv('RELEASE_TAG', 'v1.0.0-rc11')
    root = tmp_path / 'release-assets'
    root.mkdir()
    checks = {}
    for name in ('CodexTeam-Setup-x64.exe', 'CodexTeam-Setup-x64.zip', 'CodexTeam-Portable-x64.zip'):
        data = ('synthetic contract fixture: ' + name).encode()
        (root / name).write_bytes(data)
        checks[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    (root / 'release-checksums.json').write_text(json.dumps(checks))
    (root / 'SHA256SUMS.txt').write_text(''.join(f"{entry['sha256']}  {name}\n" for name, entry in checks.items()))
    (root / 'build-verification.json').write_text(json.dumps({'app_version': '1.0.0rc11', 'sensitive_paths_found': 0, 'required_files_checked': 30}))
    (root / 'BUILD-NOTES.txt').write_text('Source commit: ' + 'a' * 40 + '\nFull source suite: passed.')
    (root / 'RELEASE-NOTES-RU.md').write_text('Synthetic release validation fixture')
    smoke = {'platform': 'Windows', 'installed_backend_verified': True, 'uninstall_verified': True,
             'model_calls': 0, 'sdk_account_calls': 0, 'installed_git_version': 'git version fixture', 'runtime_version': '1.0.0-rc11'}
    portable = {'platform': 'Windows', 'source_commit': 'a' * 40, 'model_calls': 0, 'sdk_account_calls': 0, 'runtime_version': '1.0.0-rc11'}
    portable.update({gate: True for gate in ('archive_crc_verified', 'startup_verified', 'restart_verified', 'settings_history_queue_preserved', 'portable_backend_verified')})
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    path = root / 'installed-smoke.json'
    path.write_text(json.dumps(smoke))
    with pytest.raises(AssertionError, match='Missing native release gate'):
        exec(script, {})
    gates = ('start_menu_shortcut_verified', 'project_doctor_verified', 'queue_preflight_verified', 'same_version_upgrade_verified',
             'uninstall_data_preservation_verified', 'reinstall_restart_verified',
             'mission_queue_restart_verified', 'appearance_restart_verified', 'notebook_restart_verified')
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
    portable['portable_backend_verified'] = False
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    with pytest.raises(AssertionError, match='Missing portable release gate'):
        exec(script, {})
    portable['portable_backend_verified'] = True
    (root / 'portable-smoke.json').write_text(json.dumps(portable))
    (root / 'BUILD-NOTES.txt').write_text('Source commit: ' + 'a' * 40 + '\nFull source suite: skipped by explicit manual request.')
    with pytest.raises(AssertionError):
        exec(script, {})
