import pytest

from codex_team.evidence import is_test_execution, successful_test_execution
from codex_team.runtimes import powershell_python_process


def command(script, output="Ran 4 tests in 0.1s\nOK", exit_code=0):
    return {"command": script, "actions": [{"type": "unknown", "command": script}],
            "status": "completed", "exit_code": exit_code, "output": output}


@pytest.fixture
def wrapper():
    return powershell_python_process([r"C:\Program Files\Codex Team\runtime\python\python.exe", "-I", "-B", "-c",
        "import unittest; suite=unittest.defaultTestLoader.discover(r'C:\\project'); result=unittest.TextTestRunner().run(suite); raise SystemExit(0 if suite.countTestCases()>0 and result.wasSuccessful() else 1)"],
        r"C:\Program Files\Codex Team\runtime\python\Lib")


def test_process_wrapper_recognized_and_actual_output_required(wrapper):
    assert is_test_execution(command(wrapper))
    assert successful_test_execution(command(wrapper))
    assert not successful_test_execution(command(wrapper, output=""))
    assert not successful_test_execution(command(wrapper, exit_code=1))
    assert not successful_test_execution(command(wrapper, output="Ran 0 tests\nOK"))
    assert not successful_test_execution(command(wrapper, output="Ran 4 tests\nFAILED (failures=1)"))


@pytest.mark.parametrize("old,new", [
    ("$testProcess.Start()", "$testProcess.NotStart()"),
    ("$testProcess.WaitForExit()", "$testProcess.NotWait()"),
    ("exit $testProcess.ExitCode", "exit 0"),
    ("exit $testProcess.ExitCode", "exit $otherProcess.ExitCode"),
    ("UseShellExecute = $false", "UseShellExecute = $true"),
    ("python.exe", "echo.exe"),
])
def test_incomplete_or_mismatched_process_evidence_rejected(wrapper, old, new):
    assert not is_test_execution(command(wrapper.replace(old, new)))


def test_printing_process_or_runner_source_cannot_fabricate_execution(wrapper):
    assert not is_test_execution(command("Write-Output @'\n" + wrapper + "\n'@"))
    fake = powershell_python_process([r"C:\Python\python.exe", "-c",
        "print('unittest.TextTestRunner().run(suite)'); print('Ran 4 tests\\nOK')"], r"C:\Python\Lib")
    assert not is_test_execution(command(fake))
    assert not is_test_execution(command(fake + "\n# unittest.TextTestRunner().run(suite)"))


def test_reassigned_process_executable_not_accepted(wrapper):
    changed = wrapper.replace("if (-not $testProcess.Start())", "$testProcess.StartInfo.FileName = 'C:\\fake\\echo.exe'\nif (-not $testProcess.Start())")
    assert not is_test_execution(command(changed))


def test_observed_base64_here_string_qa_process_tracks_exact_variable_chain(wrapper):
    prefix = "$qaCode = @'\nimport unittest\nsuite=unittest.TestSuite()\nresult=unittest.TextTestRunner().run(suite)\n'@\n$qaEncoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($qaCode))\n"
    lines = wrapper.splitlines()
    lines = [line if ".Arguments =" not in line else "$testProcess.StartInfo.Arguments = '-I -B -c \"import base64; exec(base64.b64decode(''' + $qaEncoded + '''))\"'" for line in lines]
    observed = prefix + "\n".join(lines)
    assert is_test_execution(command(observed))
    assert not is_test_execution(command(observed.replace("GetBytes($qaCode)", "GetBytes($fakeCode)")))
    assert not is_test_execution(command(observed.replace("result=unittest.TextTestRunner().run(suite)", "print('Ran 4 tests\\nOK')")))
    assert not is_test_execution(command(observed.replace("exec(base64.b64decode(", "print(base64.b64decode(")))
    assert not is_test_execution(command(observed.replace("$qaEncoded = [Convert]", "$qaCode = 'print(1)'\n$qaEncoded = [Convert]")))


def test_direct_python_literal_mentions_are_not_test_invocations():
    assert not is_test_execution(command('python -c "print(\'unittest.TextTestRunner().run(suite)\')"'))
    assert not is_test_execution(command('python -c "print(\'pytest.main([])\')"'))


@pytest.mark.parametrize('executable', [
    'python', 'python3', 'python3.12', '/usr/bin/python3.12',
    "'/opt/Python Runtime/bin/python3.13'", '"C:\\Python\\python3.12.exe"',
])
def test_versioned_python_test_invocations_are_recognized(executable):
    script = executable + " -c 'import unittest; unittest.main()'"
    assert successful_test_execution(command(script))


@pytest.mark.parametrize('executable', [
    'notpython3.12', '/tmp/notpython3.12', 'python3.12-backup',
    "'/tmp/notpython3.12'", 'python3.12.exe.bak',
])
def test_similar_executable_names_do_not_fabricate_test_execution(executable):
    assert not is_test_execution(command(executable + " -c 'import unittest; unittest.main()'"))
