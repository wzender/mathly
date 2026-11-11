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


# ---- activity (how many people used the app on each of the last 7 or 30 days) ----

def test_activity_counts_people_per_israel_day_with_empty_days_and_the_range_total(monkeypatch):
    from datetime import datetime, timezone
    c = client()
    store = c.app.state.store
    now = datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc)                         # 12:00 in Israel, Wednesday 11.11
    monkeypatch.setattr(clock, "now", lambda: now)
    today = clock.school_day()
    store.add_answer("a", "s", "k1", True, True, None, today)
    store.add_answer("a", "s", "k2", False, True, None, today)
    store.add_answer("b", "s", "k1", True, True, None, today - timedelta(days=2))
    store.add_answer("old", "s", "k1", True, True, None, today - timedelta(days=7))      # one day before the 7-day range
    late = datetime(2026, 11, 9, 22, 30, tzinfo=timezone.utc)                         # 00:30 on 10.11 in Israel
    store.create_attempt("c", "quiz", "t", late, late + timedelta(minutes=45), [])
    store.create_attempt("a", "quiz", "t", now, now + timedelta(minutes=45), [])
    got = c.get("/api/dev/activity?days=7", headers=auth(DEV)).json()
    assert got["from"] == "2026-11-05" and got["to"] == "2026-11-11" and len(got["days"]) == 7
    by = {d["day"]: d for d in got["days"]}
    assert by["2026-11-11"] == {"day": "2026-11-11", "users": 1, "answers": 2, "attempts": 1}     # "a" once, however much they did
    assert by["2026-11-10"]["users"] == 1 and by["2026-11-10"]["attempts"] == 1                  # the attempt counts on Israel's day
    assert by["2026-11-09"]["users"] == 1 and by["2026-11-05"]["users"] == 0
    assert got["users"] == 3 and got["answers"] == 3 and got["attempts"] == 2                    # different people over the week
    month = c.get("/api/dev/activity?days=30", headers=auth(DEV)).json()
    assert len(month["days"]) == 30 and month["users"] == 4


def test_activity_is_for_developers_only_and_takes_7_or_30_days():
    c = client()
    assert c.get("/api/dev/activity").status_code == 401
    assert c.get("/api/dev/activity", headers=auth(TEACHER)).status_code == 403
    assert c.get("/api/dev/activity?days=9", headers=auth(DEV)).status_code == 422
    got = c.get("/api/dev/activity", headers=auth(DEV)).json()
    assert len(got["days"]) == 7 and got["users"] == 0
    assert "user_id" not in json.dumps(got)                                             # counts only, never who


def test_the_supabase_store_reads_the_activity_view_in_pages_after_the_last_row_read(monkeypatch):
    from datetime import date
    from mathly2.store import SupabaseStore
    s = SupabaseStore("https://x.invalid", "secret")
    monkeypatch.setattr(SupabaseStore, "ACTIVITY_PAGE", 2)
    table = [{"day": d, "user_id": u, "answers": 1, "attempts": 0} for d, u in
             (("2026-11-09", "u1"), ("2026-11-10", "u1"), ("2026-11-10", "u3"), ("2026-11-10", "u5"), ("2026-11-11", "u2"))]
    asked = []
    def fake(method, table_name, params=None, **kw):
        asked.append(params.get("or"))
        if len(asked) == 2:                                          # a new row lands before the page already read
            table.insert(1, {"day": "2026-11-09", "user_id": "u0", "answers": 1, "attempts": 0})
            table.sort(key=lambda r: (r["day"], r["user_id"]))
        rows = table
        if params.get("or"):                                         # day.gt.D or (day.eq.D and user_id.gt.U)
            d = params["or"].split("day.gt.")[1].split(",")[0]
            u = params["or"].split("user_id.gt.")[1].rstrip("))")
            rows = [r for r in table if r["day"] > d or (r["day"] == d and r["user_id"] > u)]
        return rows[:int(params["limit"])]
    monkeypatch.setattr(s, "_request", fake)
    got = s.activity_since(date(2026, 11, 5))
    assert [(r["day"].isoformat(), r["user_id"]) for r in got] == [("2026-11-09", "u1"), ("2026-11-10", "u1"), ("2026-11-10", "u3"),
                                                                   ("2026-11-10", "u5"), ("2026-11-11", "u2")]   # each once, none skipped
    assert asked == [None, "(day.gt.2026-11-10,and(day.eq.2026-11-10,user_id.gt.u1))",
                     "(day.gt.2026-11-10,and(day.eq.2026-11-10,user_id.gt.u5))"]
