"""The dashboard shows which git commit the server is running."""
from evorium import main


def test_version_reads_the_git_commit():
    v = main.code_version()
    assert len(v["commit"]) >= 7 and v["commit"] != "unknown"
    assert v["subject"] and v["date"]
    assert isinstance(v["modified"], bool)


def test_version_outside_a_git_checkout(tmp_path):
    v = main.code_version(tmp_path)
    assert v == {"commit": "unknown", "date": "", "subject": "Not a git checkout", "modified": False}


def test_usage_reports_the_version(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from evorium.db import init_db
    from evorium.seed import seed_agents
    path = tmp_path / "world.sqlite3"
    init_db(path); seed_agents(path)
    monkeypatch.setattr(main, "DEFAULT_DB_PATH", path)   # never the real world
    data = TestClient(main.app).get("/usage").json()
    assert data["version"]["commit"] == main.VERSION["commit"]
