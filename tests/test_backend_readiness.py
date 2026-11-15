"""Actual app.js DOM/transport integration via existing synthetic harness; no native claim."""
from pathlib import Path
import json
import subprocess
import shutil
import pytest

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'codex_team/static'

@pytest.mark.parametrize('scenario',['initial','status-failed','health-failed','delayed-status','auth-required','stable-label','recovery'])
def test_app_local_readiness_is_independent_of_sdk(scenario):
    node=shutil.which('node')
    if not node:pytest.skip('Node required for browser contract')
    result=subprocess.run([node,str(ROOT/'tests/ui_smoke.cjs'),str(STATIC),scenario],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)['scenario']==scenario


def test_late_health_response_cannot_override_newer_readiness():
    node=shutil.which('node')
    if not node:pytest.skip('Node required for transport contract')
    result=subprocess.run([node,str(ROOT/'tests/backend_readiness.cjs'),str(STATIC)],capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert json.loads(result.stdout)['result']=='PASS'
