"""Local UI contracts. Synthetic HTTP/DOM only; no Codex or paid API calls."""
from collections import Counter
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest


REPOSITORY = Path(__file__).resolve().parents[1]
STATIC = Path(os.environ.get("CODEX_TEAM_UI_DIR", REPOSITORY / "codex_team" / "static"))


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.assets = []
        self.secret_input = None

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "script" and attrs.get("src"):
            self.assets.append(attrs["src"])
        if tag == "link" and attrs.get("rel") == "stylesheet":
            self.assets.append(attrs.get("href", ""))
        if attrs.get("id") == "api-key-input":
            self.secret_input = attrs


def test_ui_has_unique_control_ids_and_no_remote_assets():
    markup = Markup()
    markup.feed((STATIC / "index.html").read_text(encoding="utf-8-sig"))
    duplicates = [key for key, count in Counter(markup.ids).items() if count > 1]
    assert duplicates == []
    assert all(not asset.startswith(("http:", "https:", "//")) for asset in markup.assets)
    assert markup.secret_input["type"] == "password"
    assert "value" not in markup.secret_input


def test_agent_output_cannot_reach_html_execution_sinks():
    script = (STATIC / "app.js").read_text(encoding="utf-8-sig")
    assert not re.search(r"\.(?:innerHTML|outerHTML)\s*=|insertAdjacentHTML\s*\(|document\.write\s*\(", script)
    assert not re.search(r"\beval\s*\(|new\s+Function\s*\(", script)


def test_browser_behaviour_uses_explicit_provider_and_action_contracts():
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for the synthetic UI contract test")
    script = Path(__file__).with_name("ui_smoke.cjs")
    if not script.exists():
        script = Path(__file__).with_name("smoke.cjs")
    result = subprocess.run(
        [node, str(script), str(STATIC)], capture_output=True, text=True,
        encoding="utf-8", timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip())
    assert report["result"] == "PASS"
    assert "resume exact total budget" in report["evidence"]
    assert "canonical role model defaults" in report["evidence"]
