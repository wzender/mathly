"""The morning report (report.py): one day's practice in counts, read by the developer or with REPORT_TOKEN."""
from datetime import timedelta

from fastapi.testclient import TestClient

from mathly2 import clock
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.test_boardwork_api import auth, uid

KID, KID2, TEACHER, DEV = "kid@school.test", "kid2@school.test", "t@school.test", "dev@school.test"
TOKEN = "a-long-random-report-token"


def world(token=TOKEN):
    store = InMemoryStore()
    klass = store.create_class("setup", "ט מצוינות", lessons=["t"], teacher_email=TEACHER)
    for who in (KID, KID2):
        store.add_member(klass["id"], who)
    client = TestClient(create_app(Settings(teachers=frozenset({TEACHER}), developers=frozenset({DEV}), report_token=token), store=store))
    for who in (KID, KID2):
        client.get("/api/me", headers=auth(who))
    return client, store


def test_yesterdays_practice_in_counts_by_kind_and_class_with_the_week():
    client, store = world()
    yesterday = clock.school_day() - timedelta(days=1)
    for i in range(6):
        store.add_answer(uid(KID), "t_ext", f"t_ext:{i}", i != 5, True, None, yesterday)
    store.add_answer(uid(KID2), "t_ext", "t_ext:1", True, True, None, yesterday - timedelta(days=2))
    when = clock.now() - timedelta(days=1)
    done = store.create_attempt(uid(KID), "onthego_round", "math", when, when + timedelta(days=1), [])
    store.save_attempt(done["id"], submitted_at=when)
    store.create_attempt(uid(KID), "lesson_round", "t", when, when + timedelta(days=1), [])
    got = client.get("/api/dev/report", headers={"Authorization": f"Bearer {TOKEN}"}).json()
    assert got["day"] == yesterday.isoformat() and got["answers"] == 6 and got["correct"] == 5 and got["people"] == 1
    assert got["kinds"]["onthego_round"] == {"started": 1, "finished": 1} and got["kinds"]["lesson_round"] == {"started": 1, "finished": 0}
    assert got["classes"] == [{"name": "ט מצוינות", "students": 2, "active": 1, "answers": 6}]
    assert len(got["week"]) == 7 and got["week"][-1] == {"day": yesterday.isoformat(), "people": 1, "answers": 6}
    assert got["week"][-3]["answers"] == 1
    assert KID not in str(got) and KID2 not in str(got)                                        # counts only


def test_the_token_or_the_developer_and_nobody_else():
    client, store = world()
    assert client.get("/api/dev/report", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/dev/report").status_code == 401
    assert client.get("/api/dev/report", headers=auth(TEACHER)).status_code == 403
    assert client.get("/api/dev/report", headers=auth(DEV)).status_code == 200
    assert client.get("/api/dev/report?day=2026-11-20", headers=auth(DEV)).json()["day"] == "2026-11-20"
    assert client.get("/api/dev/report?day=bad", headers=auth(DEV)).status_code == 422
    no_token, _ = world(token="")
    assert no_token.get("/api/dev/report", headers={"Authorization": "Bearer "}).status_code == 401   # no token set: the developer only


def test_the_supabase_reads_ask_for_one_day():
    from datetime import date
    from mathly2.tests.test_store import Recorder
    s = Recorder([[{"user_id": "u", "correct": 4}], [{"kind": "quiz", "user_id": "u", "submitted_at": None}]])
    assert s.correct_on(date(2026, 11, 21)) == {"u": 4}
    assert s.calls[0][1] == "m2_daily_correct" and s.calls[0][2]["day"] == "eq.2026-11-21"
    assert s.attempts_started_on(date(2026, 11, 21)) == [{"kind": "quiz", "user_id": "u", "submitted_at": None}]
    where = s.calls[1][2]["and"]
    assert s.calls[1][1] == "m2_attempts" and "started_at.gte.2026-11-21T00:00:00+02:00" in where and "started_at.lt.2026-11-22T00:00:00+02:00" in where
