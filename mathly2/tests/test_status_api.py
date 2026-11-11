"""The developer's status card (DEV-5): only a developer reads it; it reports each part, the version and the update date,
and never a key."""
import base64
import json
import subprocess
from dataclasses import replace
from datetime import timedelta

from fastapi.testclient import TestClient

from mathly2 import clock, status, version
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore, StoreUnavailable

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
    vapid = base64.urlsafe_b64encode(bytes(range(1, 33))).rstrip(b"=").decode()          # a valid 32-byte key
    got = client(anthropic_key="sk-secret-value", vapid_private_key=vapid).get("/api/dev/status", headers=auth(DEV))
    states = {c["key"]: c["state"] for c in got.json()["checks"]}
    assert states["ai"] == "ok" and states["push"] == "ok"
    assert "secret-value" not in got.text and vapid not in got.text


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


def test_a_set_but_invalid_push_key_is_an_error():
    got = client(vapid_private_key="not-a-key").get("/api/dev/status", headers=auth(DEV)).json()
    push = next(c for c in got["checks"] if c["key"] == "push")
    assert push["state"] == "error" and got["overall"] == "error"


class Down(InMemoryStore):
    def __getattribute__(self, name):
        if name in ("roles_of", "classes_taught", "classes_of_student"):
            raise StoreUnavailable("down")
        return super().__getattribute__(name)


def test_the_card_still_opens_for_a_developer_when_the_database_is_down():
    app = create_app(Settings(developers=frozenset({DEV})), store=Down())
    app.state.settings = replace(app.state.settings, supabase_url="https://x.invalid", supabase_key="k", supabase_secret="s")
    got = TestClient(app).get("/api/dev/status", headers=auth(DEV))
    assert got.status_code == 200
    db = next(c for c in got.json()["checks"] if c["key"] == "database")
    assert db["state"] == "error" and got.json()["overall"] == "error"


def test_the_git_fallback_reads_the_last_commit(tmp_path):
    run = lambda *a: subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    run("init", "-q")
    (tmp_path / "f").write_text("x")
    run("add", "f")
    run("-c", "user.name=t", "-c", "user.email=t@t.test", "commit", "-q", "-m", "one")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.strip()
    got = version.read(tmp_path / "missing.json", tmp_path)
    assert got["source"] == "git" and got["commit"] == sha and got["short"] == sha[:7] and got["date"].startswith("20")


def test_the_version_file_wins_then_git_then_nothing(tmp_path):
    f = tmp_path / "version.json"
    f.write_text(json.dumps({"commit": "b" * 40, "date": "2026-11-10T22:00:00+00:00"}))
    assert version.read(f, tmp_path) == {"commit": "b" * 40, "short": "bbbbbbb", "date": "2026-11-10T22:00:00+00:00", "source": "file"}
    assert version.read(tmp_path / "missing.json", tmp_path / "nowhere") == {"commit": None, "short": None, "date": None, "source": None}
    for bad in ("not json", "[1, 2]", "\"text\"", "{\"commit\": 5}"):
        f.write_text(bad)
        assert version.read(f, tmp_path / "nowhere")["source"] is None
