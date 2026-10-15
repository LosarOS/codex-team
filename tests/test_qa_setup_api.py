"""QA setup HTTP contracts; no images pulled and no project commands executed."""
from test_server import local_app
from test_suite_integration import project
from codex_team.qa_arena import DockerRunner


def test_setup_metadata_and_explicit_verification_contract(local_app, monkeypatch):
    client, app, root, db, repo = local_app
    pid = project(client, repo)
    image = {"id": "sha256:" + "b" * 64, "tags": ["local:fixture"], "digests": [], "size_bytes": 1024, "os_type": "linux"}
    monkeypatch.setattr(DockerRunner, "inspect_daemon", lambda self: {"available": True, "healthy": True, "local": True, "os_type": "linux", "endpoint": "unix:///local/fixture.sock", "daemon_id": "fixture"})
    monkeypatch.setattr(DockerRunner, "images", lambda self: [image])
    inspected = []
    def inspect(self, value):
        inspected.append(value)
        return image
    monkeypatch.setattr(DockerRunner, "inspect_image", inspect)
    def no_execution(*args, **kwargs):
        raise AssertionError("Setup wizard cannot execute containers or test commands")
    monkeypatch.setattr(DockerRunner, "execute", no_execution)
    response = client.get(f"/api/suite/projects/{pid}/qa/setup")
    assert response.status_code == 200, response.text
    setup = response.json()
    assert setup["images"] == [image]
    assert setup["docker"]["healthy"]
    assert setup["test_run_requires_confirmation"]
    assert setup["automatic_pull"] is False and setup["automatic_install"] is False
    assert inspected == []
    url = f"/api/suite/projects/{pid}/qa/setup/verify"
    assert client.post(url, json={"image": image["id"]}).status_code == 400
    assert client.post(url, json={"image": image["id"], "confirmed": False}).status_code == 400
    assert inspected == []
    verified = client.post(url, json={"image": image["id"], "confirmed": True})
    assert verified.status_code == 200, verified.text
    assert verified.json()["available"]
    assert verified.json()["tools_executed"] is False
    assert verified.json()["pinned_image"] == image["id"]
    assert inspected == [image["id"]]
    assert client.get("/api/suite/qa", params={"project_id": pid}).json()["total"] == 0
    assert client.get(f"/api/suite/projects/{pid}/qa/config").json() is None


def test_setup_api_handles_missing_docker_and_retains_local_boundaries(local_app, monkeypatch):
    client, app, root, db, repo = local_app
    pid = project(client, repo)
    monkeypatch.setattr("codex_team.qa_arena.shutil.which", lambda _: None)
    url = f"/api/suite/projects/{pid}/qa/setup"
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["docker"]["available"] is False
    assert response.json()["images"] == []
    assert response.json()["remediation"]
    verified = client.post(url + "/verify", json={"image": "sha256:" + "b" * 64, "confirmed": True})
    assert verified.status_code == 200
    assert verified.json()["available"] is False
    assert client.get("/api/suite/projects/missing/qa/setup").status_code == 404
    assert client.post(url + "/verify", json={"image": "x" * 301, "confirmed": True}).status_code == 422
    assert client.post(url + "/verify", json={"image": "sha256:" + "b" * 64, "confirmed": True, "execute": True}).status_code == 422
    assert client.post(url + "/verify", json={"image": "sha256:" + "b" * 64, "confirmed": True}, headers={"origin": "http://evil.invalid"}).status_code == 403
