import asyncio
import logging
from datetime import datetime, timezone

import httpx

from app import log_errors
from app.main import create_app
from app.monitoring import activity_buckets, photo_summary, seen_summary

TEACHER, STUDENT = "teacher-token", "student-token"


class MonitorAuth:
    url, key, secret = "https://test.invalid", "public", "server"
    teachers, developers = frozenset(), frozenset({"t@test.invalid"})   # management is for developers

    def __init__(self, rows=None):
        self.rows = rows

    def user(self, token):
        return {TEACHER: {"id": "t", "email": "t@test.invalid"},
                STUDENT: {"id": "s", "email": "s@test.invalid"}}.get(token)

    def classes(self, fresh=False):
        return [{"id": 1, "name": "9א", "emails": ["s@test.invalid"], "teachers": []}]

    def access_for(self, _id, **_kwargs):
        return None

    def ping(self):
        return {"auth": {"ok": True, "ms": 12}, "db": {"ok": True, "ms": 30}}

    def answer_activity(self, since):
        return self.rows


def get(app, path, token):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            return await client.get(path, headers={"Authorization": f"Bearer {token}"})
    return asyncio.run(run())


def test_monitoring_is_for_managers_only():
    app = create_app(MonitorAuth())
    for path in ("/api/monitor/summary", "/api/monitor/supabase", "/api/monitor/activity"):
        assert get(app, path, STUDENT).status_code == 403
        assert get(app, path, TEACHER).status_code == 200


def test_summary_counts_sign_ins_photos_and_log_errors():
    app = create_app(MonitorAuth())
    get(app, "/api/me", STUDENT)
    today = datetime.now().astimezone().date().isoformat()
    app.state.photo_counts.update({("s@test.invalid", today): 2, ("x@test.invalid", "2000-01-01"): 5})
    logging.getLogger("mathly.test").error("something broke")
    data = get(app, "/api/monitor/summary", TEACHER).json()
    assert data["seen"]["last_5m"] == 2  # the student and the teacher asking
    assert data["build"]["version"]
    assert data["errors"]["recent"][0]["message"] == "something broke"
    assert data["answers"]["open_ended_locked"] is True
    assert get(app, "/api/monitor/supabase", TEACHER).json()["db"]["ok"] is True


def test_activity_buckets_and_missing_tables():
    now = datetime(2026, 11, 1, 12, 7, tzinfo=timezone.utc)
    rows = {"attempts": [{"user_id": "a", "created_at": "2026-11-01T12:01:00.123+00:00"},
                         {"user_id": "a", "created_at": "2026-10-31T09:00:00+00:00"},
                         {"user_id": "b", "created_at": "2026-11-01T12:02:00+00:00"},
                         {"user_id": "c", "created_at": "2026-09-01T12:00:00+00:00"}],
            "grades": [{"user_id": "a", "state": "completed", "verdict": "correct", "created_at": "2026-11-01T12:03:00+00:00"},
                       {"user_id": "b", "state": "failed", "verdict": None, "created_at": "2026-11-01T12:04:00+00:00"}]}
    day = activity_buckets(rows, "day", now)
    assert len(day["buckets"]) == 96 and day["buckets"][-1] == {
        "bucket": "2026-11-01T12:00:00+00:00", "attempts": 2, "active_students": 2}
    assert day["summary"]["attempts"] == 2
    week = activity_buckets(rows, "week", now)["summary"]
    assert week == {"attempts": 3, "active_students": 2, "returning_students": 1, "active_days": 2,
                    "checks": 2, "verdicts": {"correct": 1, "failed": 1}}
    month = activity_buckets(rows, "month", now)
    assert len(month["buckets"]) == 30 and month["summary"]["attempts"] == 3

    app = create_app(MonitorAuth(rows=None))
    assert "unavailable" in get(app, "/api/monitor/activity?period=day", TEACHER).json()
    assert get(app, "/api/monitor/activity?period=year", TEACHER).status_code == 422


def test_small_summaries():
    assert seen_summary({"old": 0, "hour": 98_000.0, "new": 100_000.0}, now=100_100.0) == {"last_5m": 1, "last_hour": 2, "last_24h": 2}
    assert photo_summary({("a", "d"): 20, ("b", "d"): 1, ("c", "e"): 3}, today="d") == {
        "today": 21, "students": 2, "at_limit": 1, "daily_limit": photo_summary({}, "d")["daily_limit"]}
    assert log_errors.COUNTER in logging.getLogger().handlers


def test_recent_actions_name_the_action_and_the_user():
    app = create_app(MonitorAuth())
    get(app, "/api/me", STUDENT)
    get(app, "/api/me", STUDENT)  # a page reload soon after is the same visit
    app.state.actions.record("s", "answer_upload", "Question 1")  # answer routes pass the user id
    actions = get(app, "/api/monitor/summary", TEACHER).json()["actions"]
    assert [(a["kind"], a["email"], a["label"]) for a in actions] == [
        ("visit", "t@test.invalid", ""), ("answer_upload", "s@test.invalid", "Question 1"),
        ("visit", "s@test.invalid", "")]
