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
    script = "\n".join(path.read_text(encoding="utf-8-sig") for path in STATIC.glob("*.js"))
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


def test_mission_control_projects_persisted_attempts_and_activity():
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for Mission Control projection tests")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("mission_control.cjs")), str(STATIC)],
        capture_output=True, text=True, encoding="utf-8", timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout.strip())["result"] == "PASS"


def test_shared_api_client_bounds_requests_and_reports_errors():
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for shared transport tests")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("api_client.cjs")), str(STATIC)],
        capture_output=True, text=True, encoding="utf-8", timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_primary_markup_uses_russian_labels_instead_of_internal_terms():
    class Copy(HTMLParser):
        def __init__(self):
            super().__init__()
            self.labels = []

        def handle_data(self, data):
            self.labels.append(data)

        def handle_starttag(self, tag, attributes):
            attrs = dict(attributes)
            self.labels.extend(attrs.get(key, "") for key in ("title", "aria-label", "placeholder", "alt"))

    copy = Copy()
    copy.feed((STATIC / "index.html").read_text(encoding="utf-8-sig"))
    assert not re.search(
        r"\b(?:provider|workspace|API key|Reasoning effort|Quality Gate|Baseline|Mission Control)\b|LOCAL CONTROL CENTER|OFFICIAL CODEX SDK",
        "\n".join(copy.labels), re.IGNORECASE,
    )


def test_builtin_pack_titles_and_descriptions_are_russian():
    for path in (REPOSITORY / "packs").glob("*.json"):
        pack = json.loads(path.read_text(encoding="utf-8"))
        assert re.search("[А-Яа-яЁё]", pack["title"]) or pack["title"] == "ELMA365"
        assert re.search("[А-Яа-яЁё]", pack["description"])
        assert pack["name"] == path.stem


def test_localization_preserves_user_data_and_contract_keys():
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for localization contracts")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("i18n.cjs")), str(STATIC)],
        capture_output=True, text=True, encoding="utf-8", timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.strip())
    assert report["result"] == "PASS"
    assert report["catalog"] >= 1000


def test_suite_retains_actionable_localized_error_messages():
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for localized error contracts")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("suite_messages.cjs")), str(STATIC)],
        capture_output=True, text=True, encoding="utf-8", timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_builtin_pack_copy_localizes_without_changing_custom_content():
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for pack localization contracts")
    result = subprocess.run(
        [node, str(Path(__file__).with_name("pack_localization.cjs")), str(STATIC)],
        capture_output=True, text=True, encoding="utf-8", timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("script", ["refresh_loop.cjs", "task_drafts.cjs", "command_palette.cjs", "task_templates.cjs", "run_comparison.cjs", "run_notebook.cjs"])
def test_productivity_and_recovery_contracts(script):
    node = os.environ.get("CODEX_TEAM_TEST_NODE") or shutil.which("node")
    if not node:
        pytest.skip("Node.js is needed for browser module contracts")
    result = subprocess.run([node, str(Path(__file__).with_name(script)), str(STATIC)],
                            capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
