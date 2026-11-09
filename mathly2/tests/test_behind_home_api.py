"""Lessons behind the curriculum on the home (add-behind-lessons-to-home 1.1)."""
from datetime import timedelta

from mathly2 import clock
from mathly2.tests.test_quizzes_api import take
from mathly2.tests.test_skills_api import KID, KID_ID, MON, auth, raw, world  # noqa: F401

STAMP = "2026-10-05T10:00:00+00:00"


def behind(client):
    return client.get("/api/home", headers=auth()).json()["behind"]


def skills_of(bank, lesson):
    return [s["id"] for s in bank.skills if s["unit"] == lesson]


def test_every_lesson_behind_is_listed_earliest_date_first_and_others_are_not(world):
    client, store, bank = world
    today = clock.school_day()
    store.set_lesson_dates({"t": today - timedelta(days=2), "t2": today - timedelta(days=9), "k": today + timedelta(days=5), "i": today})      # t2 and t behind; k ahead; i is due today
    got = behind(client)
    assert [r["id"] for r in got] == ["t2", "t"] and got[0]["due_date"] == (today - timedelta(days=9)).isoformat()
    assert all(r["name"] for r in got)
    for s in skills_of(bank, "t2"):
        store.save_progress(KID_ID, s, started_at=STAMP, mastered_at=STAMP)
    assert [r["id"] for r in behind(client)] == ["t"]                                                          # completed: no longer listed


def test_a_lesson_without_a_date_is_never_listed_and_none_behind_means_an_empty_list(world):
    client, store, bank = world
    assert behind(client) == []
    store.set_lesson_dates({"k": clock.school_day() + timedelta(days=3)})
    assert behind(client) == []


def test_a_behind_lesson_has_only_the_quiz_and_no_skills_option(world):
    client, store, bank = world
    store.set_lesson_dates({"t": clock.school_day() - timedelta(days=1)})
    row = behind(client)[0]
    assert set(row) == {"id", "name", "due_date", "quiz"} and "next_skill" not in row and "mastered" not in row          # nothing about finishing the skills


def test_the_quiz_option_shows_the_best_grade_and_what_is_needed_and_a_pass_catches_the_lesson_up(world):
    client, store, bank = world
    store.set_lesson_dates({"t": clock.school_day() - timedelta(days=1)})
    assert behind(client)[0]["quiz"] == {"best": None, "open": False, "pass_right": 13, "size": 15}
    take(client, bank, "t", [True] * 12 + [False] * 3)                                                         # 80
    quiz = behind(client)[0]["quiz"]
    assert quiz["best"] == 80 and quiz["pass_right"] == 13 and quiz["size"] == 15
    take(client, bank, "t", [True] * 13 + [False] * 2)                                                         # passed
    assert behind(client) == []


def test_the_path_and_the_home_agree_on_what_is_behind(world):
    client, store, bank = world
    today = clock.school_day()
    store.set_lesson_dates({"t": today - timedelta(days=4), "t2": today - timedelta(days=1)})
    path = client.get("/api/path", headers=auth()).json()
    assert {l["id"] for l in path["lessons"] if l["behind"]} == {r["id"] for r in behind(client)} == {"t", "t2"} and path["behind"] == 2


def weak(client):
    return client.get("/api/home", headers=auth()).json()["weak_tests"]


def exercise(store, test, number, grade, when_offset=0):
    row = store.create_attempt(KID_ID, "exercise_test", f"{test['id']}:{number}", MON, MON + timedelta(minutes=45), [])
    store.save_attempt(row["id"], submitted_at=MON + timedelta(minutes=10 + when_offset), grade=grade)


def test_practice_tests_below_87_are_listed_and_not_taken_or_good_ones_are_not(world):
    client, store, bank = world
    test = store.create_test(1, clock.school_day() + timedelta(days=10), ["t"], "t@x.test", created_at=clock.now() - timedelta(days=20))
    assert weak(client) == []                                                                                    # none taken
    exercise(store, test, 1, 25)
    got = weak(client)
    assert got == [{"test_id": test["id"], "date": test["date"].isoformat(), "days_left": 10, "number": 1, "best": 25, "open": False}]
    exercise(store, test, 2, 87)                                                                                 # 13 of 15: good enough
    assert [(w["number"], w["best"]) for w in weak(client)] == [(1, 25)]
    exercise(store, test, 1, 86, 1)                                                                              # a retake still below: the best of the two
    assert weak(client)[0]["best"] == 86
    exercise(store, test, 1, 90, 2)
    assert weak(client) == []                                                                                    # reached: no longer listed


def test_a_past_test_is_not_listed(world):
    client, store, bank = world
    old = store.create_test(1, clock.school_day() - timedelta(days=3), ["t"], "t@x.test", created_at=clock.now() - timedelta(days=30))
    exercise(store, old, 1, 10)
    assert weak(client) == []


def test_only_the_nearest_tests_weak_practice_tests_are_on_home(world):
    client, store, bank = world
    near = store.create_test(1, clock.school_day() + timedelta(days=4), ["t"], "t@x.test", created_at=clock.now() - timedelta(days=20))
    far = store.create_test(1, clock.school_day() + timedelta(days=12), ["t2"], "t@x.test", created_at=clock.now() - timedelta(days=20))
    exercise(store, far, 1, 10)
    assert weak(client) == []                                                                                    # only the farther test has one
    exercise(store, near, 2, 40)
    assert [(w["test_id"], w["number"]) for w in weak(client)] == [(near["id"], 2)]
