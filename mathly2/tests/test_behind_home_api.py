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


def test_the_skills_option_says_how_far_and_opens_the_next_unmastered_skill(world):
    client, store, bank = world
    store.set_lesson_dates({"t": clock.school_day() - timedelta(days=1)})
    skills = skills_of(bank, "t")
    for s in skills[:3]:
        store.save_progress(KID_ID, s, started_at=STAMP, mastered_at=STAMP)
    row = behind(client)[0]
    assert (row["mastered"], row["total"]) == (3, len(skills)) and row["next_skill"]["id"] == skills[3] and row["next_skill"]["name"]
    store.save_progress(KID_ID, skills[1], mastered_at=None)                                                    # a skill not mastered in the middle comes first
    assert behind(client)[0]["next_skill"]["id"] == skills[1]


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
