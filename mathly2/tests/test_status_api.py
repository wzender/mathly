"""The developer's status card (DEV-5): only a developer reads it; it reports each part, the version and the update date,
and never a key."""
import json
from datetime import timedelta

from fastapi.testclient import TestClient

from mathly2 import clock, status, version
from mathly2.config import Settings
from mathly2.main import create_app

DEV, TEACHER = "dev@school.test", "t@school.test"


def auth(email):
    return {"Authorization": f"Bearer dev:{email}"}


def client(**settings):
    return TestClient(create_app(Settings(developers=frozenset({DEV}), teachers=frozenset({TEACHER}), **settings)))


def test_only_a_developer_reads_it():
    c = client()
    assert c.get("/api/dev/status").status_code == 401
    assert c.get("/api/dev/status", headers=auth(TEACHER)).status_code == 403
    assert c.get("/api/dev/status", headers=auth(DEV)).status_code == 200


def test_without_supabase_the_memory_parts_are_warnings_and_unset_keys_are_off():
    got = client().get("/api/dev/status", headers=auth(DEV)).json()
    states = {c["key"]: c["state"] for c in got["checks"]}
    assert states == {"database": "warn", "sign_in": "warn", "bank": "ok", "ai": "off", "push": "off", "pictures": "warn", "cleanup": "off"}
    assert got["overall"] == "warn"
    bank = next(c for c in got["checks"] if c["key"] == "bank")
    assert "24 שיעורים" in bank["detail"]


def test_a_set_key_is_ok_and_its_value_is_never_returned():
    got = client(anthropic_key="sk-secret-value", vapid_private_key="vapid-secret-value").get("/api/dev/status", headers=auth(DEV))
    states = {c["key"]: c["state"] for c in got.json()["checks"]}
    assert states["ai"] == "ok" and states["push"] == "ok"
    assert "secret-value" not in got.text


def test_the_version_the_start_time_and_the_uptime(monkeypatch):
    c = client()
    started = c.app.state.started_at
    c.app.state.version = {"commit": "a" * 40, "short": "aaaaaaa", "date": "2026-11-11T07:00:00+02:00", "source": "file"}
    monkeypatch.setattr(clock, "now", lambda: started + timedelta(hours=3, minutes=5))
    got = c.get("/api/dev/status", headers=auth(DEV)).json()
    assert got["version"]["short"] == "aaaaaaa" and got["version"]["date"] == "2026-11-11T07:00:00+02:00"
    assert got["uptime_seconds"] == 3 * 3600 + 5 * 60 and got["started_at"] == started.isoformat()


class Broken:
    def roles_of(self, email):
        raise ConnectionError("down")


class Fine:
    def roles_of(self, email):
        return set()


def test_the_database_check_asks_past_the_cache_and_reports_a_failure_as_an_error():
    class Cached:
        _store = Broken()
        def roles_of(self, email):                       # the cache would answer; the check must not trust it
            return set()
    assert status._database(Cached(), True)["state"] == "error"
    assert status._database(Fine(), True)["state"] == "ok"
    assert status.overall([{"state": "ok"}, {"state": "error"}, {"state": "warn"}]) == "error"
    assert status.overall([{"state": "ok"}, {"state": "off"}]) == "ok"


def test_the_version_file_wins_then_git_then_nothing(tmp_path):
    f = tmp_path / "version.json"
    f.write_text(json.dumps({"commit": "b" * 40, "date": "2026-11-10T22:00:00+00:00"}))
    assert version.read(f, tmp_path) == {"commit": "b" * 40, "short": "bbbbbbb", "date": "2026-11-10T22:00:00+00:00", "source": "file"}
    assert version.read(tmp_path / "missing.json", tmp_path)["source"] in (None, "git")   # tmp_path is not a checkout
    assert version.read(tmp_path / "missing.json", tmp_path / "nowhere") == {"commit": None, "short": None, "date": None, "source": None}
    f.write_text("not json")
    assert version.read(f, tmp_path / "nowhere")["source"] is None
