import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest

SPEC = importlib.util.spec_from_file_location('bundle_preflight_cleanup', Path(__file__).parents[1] / 'packaging/verify_bundle.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_close_captures_children_before_sdk_close_and_only_signals_owned(monkeypatch):
    events = []
    class Process:
        def __init__(self, pid): self.pid = pid
        def children(self, recursive):
            events.append('capture'); assert recursive
            return [child]
        def terminate(self): events.append(('terminate', self.pid))
        def kill(self): events.append(('kill', self.pid))
    parent, child = Process(101), Process(102)
    monkeypatch.setattr(module.psutil, 'Process', lambda pid: parent if pid == 101 else pytest.fail('unowned PID'))
    waits = iter([([], [child]), ([], [child]), ([child], [])])
    monkeypatch.setattr(module.psutil, 'wait_procs', lambda processes, timeout: next(waits))
    client = SimpleNamespace(_proc=SimpleNamespace(pid=101), close=lambda: events.append('close'))
    module.close_preflight_client(client)
    assert events == ['capture', 'close', ('terminate', 102), ('kill', 102)]


def test_lingering_owned_process_fails_closed(monkeypatch):
    process = SimpleNamespace(pid=123, terminate=lambda: None, kill=lambda: None, status=lambda: "running")
    monkeypatch.setattr(module.psutil, 'wait_procs', lambda processes, timeout: ([], [process]))
    with pytest.raises(RuntimeError, match='123'):
        module._reap_preflight_processes([process])


def test_busy_cleanup_warns_after_bounded_retry(monkeypatch, tmp_path):
    monkeypatch.setattr(module.shutil, 'rmtree', lambda root: (_ for _ in ()).throw(PermissionError('busy')))
    times = iter([0, 1, 5])
    monkeypatch.setattr(module.time, 'monotonic', lambda: next(times))
    monkeypatch.setattr(module.time, 'sleep', lambda seconds: None)
    warnings = []
    module.cleanup_preflight_directory(tmp_path, warnings)
    assert len(warnings) == 1 and str(tmp_path) in warnings[0]


def test_busy_temp_cleanup_does_not_mask_profile_error(monkeypatch):
    monkeypatch.setattr(module, '_verify_profiles_in_directory', lambda *args: (_ for _ in ()).throw(ValueError('profile invalid')))
    monkeypatch.setattr(module, 'cleanup_preflight_directory', lambda root, warnings: warnings.append('busy cleanup'))
    warnings = []
    with pytest.raises(ValueError, match='profile invalid'):
        module.verify_permission_profiles(Path('unused'), warnings)
    assert warnings == ['busy cleanup']
