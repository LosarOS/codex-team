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
