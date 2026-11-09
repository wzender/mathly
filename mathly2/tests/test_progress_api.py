"""A class's progress for its teacher (add-class-progress-views 1.2): heat map, coverage, periods, readiness and who may read them."""
import time
from datetime import datetime, timedelta, timezone

from mathly2 import clock
from mathly2.tests.test_assignments_api import DEV, KID, KID2, MGR, MON, OTHER_TEACHER, OUTSIDER, TEACHER, auth, bank, uid, world  # noqa: F401

STAMP = "2026-10-05T10:00:00+00:00"


def progress(client, who=TEACHER, period=None, klass=None):
    q = f"?period={period}" if period else ""
    return client.get(f"/api/classes/{(klass or client.a)['id']}/progress{q}", headers=auth(who))


def lesson_of(bank, lesson_id):
    return next(l for l in bank.lessons_with_skills() if l["id"] == lesson_id)


def test_progress_is_per_lesson_with_a_state_and_never_per_skill(world, bank):
    lesson = lesson_of(bank, "t")
    first, second = lesson["skills"][0]["id"], lesson["skills"][1]["id"]
    world.store.save_progress(uid(KID), first, started_at=STAMP, mastered_at=STAMP)
    world.store.save_progress(uid(KID), second, started_at=STAMP)
    world.store.add_member(world.a["id"], "new@school.test")                                  # never signed in
    got = progress(world, period=1).json()
    rows = {s["email"]: s for s in got["students"]}
    assert set(rows) == {KID, KID2, "new@school.test"} and [l["id"] for l in got["lessons"]][0] == "t"
    assert rows[KID]["lessons"]["t"]["state"] == "learning" and rows[KID2]["lessons"]["t"]["state"] == "not_started"
    assert {c["state"] for c in rows["new@school.test"]["lessons"].values()} == {"not_started"} and rows["new@school.test"]["signed_in"] is False
    text = str(got)
    assert not any(k in text for k in ("states", "skills")) and first not in text                # nothing stands for a single skill


def test_coverage_is_the_percent_mastered_and_the_best_quiz_and_completed_or_behind(world, bank):
    lesson = lesson_of(bank, "t")
    skills = [s["id"] for s in lesson["skills"]]
    for s in skills[:3]:
        world.store.save_progress(uid(KID), s, started_at=STAMP, mastered_at=STAMP)
    q = world.store.create_attempt(uid(KID), "quiz", "t", MON - timedelta(hours=2), MON - timedelta(hours=1), [])
    world.store.save_attempt(q["id"], submitted_at=MON - timedelta(hours=1), grade=80)
    world.store.set_lesson_dates({"t": clock.school_day() - timedelta(days=3)})
    got = {s["email"]: s["lessons"]["t"] for s in progress(world, period=1).json()["students"]}
    assert got[KID] == {"state": "learning", "percent": round(300 / len(skills)), "best": 80, "completed": False, "behind": True}
    assert got[KID2] == {"state": "not_started", "percent": 0, "best": None, "completed": False, "behind": True}
    for s in skills[3:]:                                                                      # all mastered: completed, no longer behind
        world.store.save_progress(uid(KID), s, started_at=STAMP, mastered_at=STAMP)
    again = {s["email"]: s["lessons"]["t"] for s in progress(world, period=1).json()["students"]}
    assert again[KID]["percent"] == 100 and again[KID]["state"] == "completed" and again[KID]["completed"] is True and again[KID]["behind"] is False
    q2 = world.store.create_attempt(uid(KID2), "quiz", "t", MON - timedelta(hours=2), MON - timedelta(hours=1), [])
    world.store.save_attempt(q2["id"], submitted_at=MON - timedelta(hours=1), grade=87)
    assert {s["email"]: s["lessons"]["t"] for s in progress(world, period=1).json()["students"]}[KID2]["completed"] is True   # a passed quiz completes it


def test_periods_pick_lessons_by_date_or_month_and_show_the_states_as_they_were(world, bank):
    # "t" is a September lesson, "n" a March lesson; a date in the curriculum moves a lesson
    first = progress(world, period=1).json()
    second = progress(world, period=2).json()
    ids1, ids2 = [l["id"] for l in first["lessons"]], [l["id"] for l in second["lessons"]]
    assert "t" in ids1 and "n" in ids2 and "t" not in ids2 and not set(ids1) & set(ids2) and len(ids1) + len(ids2) == 24
    assert first["current_period"] == 1 and first["periods"][0]["current"] is True
    world.store.set_lesson_dates({"t": date_in(2027, 2, 15)})
    assert "t" in [l["id"] for l in progress(world, period=2).json()["lessons"]]
    # a skill mastered on 20 January: not mastered in the first period (ended 31 December), mastered in the second, seen in March
    skill = lesson_of(bank, "n")["skills"][0]["id"]
    world.store.save_progress(uid(KID), skill, started_at="2026-12-01T10:00:00+00:00", mastered_at="2027-01-20T10:00:00+00:00")
    world.set_time(datetime(2027, 3, 10, 9, 0, tzinfo=timezone.utc))
    pct = lambda data, lesson="n": {s["email"]: s["lessons"][lesson] for s in data["students"]}[KID]
    assert pct(progress(world, period=2).json())["percent"] > 0 and pct(progress(world, period=2).json())["state"] == "learning"
    world.store.set_lesson_dates({"n": date_in(2026, 12, 20)})                               # move "n" into the first period to see its past state
    past = progress(world, period=1).json()
    assert pct(past)["percent"] == 0 and pct(past)["state"] == "learning" and past["as_of"] == "2026-12-31"        # started by then, mastered only in January


def date_in(y, m, d):
    from datetime import date
    return date(y, m, d)


def test_readiness_per_student_for_the_nearest_coming_test_and_none_without(world, bank):
    assert progress(world).json()["test"] is None
    far = world.store.create_test(world.a["id"], clock.school_day() + timedelta(days=30), ["t"], TEACHER, created_at=clock.now())
    near = world.store.create_test(world.a["id"], clock.school_day() + timedelta(days=10), ["t"], TEACHER, created_at=clock.now())
    got = progress(world).json()["test"]
    assert got["id"] == near["id"] and got["days_left"] == 10
    rows = {r["email"]: r for r in got["students"]}
    assert set(rows) == {KID, KID2} and rows[KID]["readiness"]["number"] == 0 and rows[KID]["simulation"] is None and rows[KID]["practice"] is None
    assert far["id"] != near["id"]


def test_only_the_classs_teacher_or_a_developer_may_read_it(world):
    assert progress(world, TEACHER).status_code == 200 and progress(world, DEV).status_code == 200
    assert progress(world, OTHER_TEACHER).status_code == 404                                  # another teacher's class: not found
    assert progress(world, MGR).status_code == 403 and progress(world, KID).status_code == 403
    assert progress(world, TEACHER, klass=world.b).status_code == 404
    assert progress(world, period=3).status_code == 422
    assert world.get(f"/api/classes/{world.a['id']}/progress").status_code in (401, 403)


def test_a_class_of_twenty_five_needs_no_more_waits_in_a_row_than_a_class_of_two(bank):
    """Every store call waits 0.1 s: the progress screen asks for all students at once, so it takes the same time for 2 as for 25."""
    from fastapi.testclient import TestClient
    from mathly2.config import Settings
    from mathly2.main import create_app
    from mathly2.tests.test_database_waits import DELAY, SlowStore

    def took(n):
        store = SlowStore()
        klass = store.create_class("setup", "A", lessons=["t"], teacher_email=TEACHER)
        for i in range(n):
            email = f"s{i}@school.test"
            store.add_member(klass["id"], email)
            store.link_user(email, uid(email))
        store.create_test(klass["id"], clock.school_day() + timedelta(days=10), ["t"], TEACHER, created_at=clock.now())
        client = TestClient(create_app(Settings(), bank=bank, store=store))
        client.get("/api/me", headers=auth(TEACHER))
        store.slow = True
        start = time.perf_counter()
        assert client.get(f"/api/classes/{klass['id']}/progress", headers=auth(TEACHER)).status_code == 200
        return time.perf_counter() - start

    small, big = took(2), took(25)
    assert big < small + 2 * DELAY, (small, big)


def test_the_store_reads_many_students_at_once_and_does_not_mix_them():
    from mathly2.store import InMemoryStore
    store = InMemoryStore()
    a, b, c = "a", "b", "c"
    store.save_progress(a, "s1", started_at=STAMP)
    store.save_progress(b, "s2", started_at=STAMP, mastered_at=STAMP)
    store.save_progress(c, "s3", started_at=STAMP)
    store.add_answer(a, "s1", "s1:k", True, True, None, clock.school_day())
    row = store.create_attempt(a, "quiz", "t", MON, MON + timedelta(minutes=20), [])
    store.create_attempt(c, "quiz", "t", MON, MON + timedelta(minutes=20), [])
    store.create_attempt(a, "simulation", "1", MON, MON + timedelta(minutes=20), [])
    got = store.progress_of_users([a, b])
    assert set(got) == {a, b} and [r["skill_id"] for r in got[a]] == ["s1"] and got[b][0]["mastered_at"] == STAMP
    assert store.progress_of_users([]) == {} and store.progress_of_users(["nobody"]) == {"nobody": []}
    assert list(store.last_answered_users([a, b])) == [a, b] and "s1" in store.last_answered_users([a])[a] and store.last_answered_users([b])[b] == {}
    quizzes = store.attempts_of_users([a, b], "quiz")
    assert [r["id"] for r in quizzes[a]] == [row["id"]] and quizzes[b] == []
