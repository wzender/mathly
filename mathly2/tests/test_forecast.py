"""The forecast grade (forecast.py): a chance per skill from its state and latest answers, averaged over the test's skills, with a range."""
from datetime import timedelta

from mathly2 import clock, forecast
from mathly2.tests.test_realtests_api import KID, TEACHER, auth, bank, covered, finished, set_test, uid, world  # noqa: F401  (fixtures)


def test_nothing_done_is_a_wide_guess_from_the_states():
    got = forecast.compute(["a", "b"], {}, set(), {})
    assert {k: got[k] for k in ("grade", "low", "high", "answers")} == {"grade": 30, "low": 5, "high": 55, "answers": 0}
    assert got["placement"] == {"done": 0, "need": forecast.PLACEMENT} and got["league"] == 0
    assert forecast.compute(["a", "b"], {"a": "mastered", "b": "learning"}, set(), {})["grade"] == round(100 * (0.85 + 0.5) / 2)
    assert forecast.compute([], {}, set(), {}) is None


def test_right_answers_raise_a_skill_and_wrong_ones_lower_it_the_newest_most():
    base = forecast.skill_chance("learning", False, [])
    up = forecast.skill_chance("learning", False, [(True, 1.0)] * 5)
    down = forecast.skill_chance("learning", False, [(False, 1.0)] * 5)
    assert down < base < up
    newest_right = forecast.skill_chance("learning", False, [(True, 1.0), (False, 1.0)])
    newest_wrong = forecast.skill_chance("learning", False, [(False, 1.0), (True, 1.0)])
    assert newest_right > newest_wrong


def test_a_test_answer_counts_double_a_mastered_skill_has_a_floor_and_a_faded_one_loses_a_tenth():
    assert forecast.skill_chance("learning", False, [(True, 2.0)]) > forecast.skill_chance("learning", False, [(True, 1.0)])
    assert forecast.skill_chance("mastered", False, [(False, 1.0)] * 12) == forecast.MASTERED_FLOOR
    assert forecast.skill_chance("mastered", True, []) == forecast.skill_chance("mastered", False, []) * 0.9


def test_placement_until_enough_answers_then_a_league_by_the_grade():
    few = forecast.compute(["a"], {}, set(), {"a": [(True, 1.0)] * 5})
    assert few["placement"] == {"done": 5, "need": 15}
    many = forecast.compute(["a", "b"], {}, set(), {"a": [(True, 1.0)] * 8, "b": [(True, 1.0)] * 8})
    assert many["placement"] is None and many["leagues"][many["league"]]["at"] <= many["grade"]
    assert [forecast.league_of(g) for g in (0, 54, 55, 69, 70, 84, 85, 100)] == [0, 0, 1, 1, 2, 2, 3, 3]


def test_the_range_narrows_with_answers():
    widths = []
    for n in (0, 5, 20, 80, 400):
        got = forecast.compute(["a"], {}, set(), {"a": [(True, 1.0)] * n} if n else {})
        widths.append(got["high"] - got["low"])
    assert widths == sorted(widths, reverse=True) and widths[-1] >= 2 * forecast.NARROWEST - 1


def test_helped_answers_do_not_count_and_tests_come_first():
    by = forecast.answers_by_skill([{"skill_id": "a", "correct": True, "counted": False}, {"skill_id": "a", "correct": False, "counted": True}],
                                   [("a", True)])
    assert by == {"a": [(True, forecast.TEST_WEIGHT), (False, 1.0)]}


# ---- the routes ----

def test_the_test_card_the_nearest_forecast_and_the_teacher_all_carry_it(world):
    client, store, lessons = world
    client.get("/api/me", headers=auth(KID))                                                  # signed in: the class knows the account
    test = set_test(client, lessons, days=14).json()
    skills = covered(client.app.state.bank, lessons[:2])
    first = client.get(f"/api/tests/{test['id']}", headers=auth(KID)).json()["forecast"]
    assert first["grade"] == 30 and first["answers"] == 0
    for s in skills:
        for n in range(3):
            store.add_answer(uid(KID), s, f"{s}:{n}", True, True, None, clock.school_day())
    later = client.get("/api/forecast", headers=auth(KID)).json()
    assert later["test"]["id"] == test["id"] and later["forecast"]["grade"] > 30 and later["forecast"]["answers"] == 3 * len(skills)
    assert later["forecast"]["high"] - later["forecast"]["low"] < first["high"] - first["low"]
    wrong = [{"skill_id": s, "key": f"{s}:x"} for s in skills for _ in range(2)]
    finished(store, test["id"], "exercise_test", f"{test['id']}:1", 0, questions=wrong)     # a practice test with every answer wrong
    after_test = client.get("/api/forecast", headers=auth(KID)).json()["forecast"]["grade"]
    assert after_test < later["forecast"]["grade"]                                            # honest: a bad test lowers it
    teacher = client.get("/api/teaching/tests", headers=auth(TEACHER)).json()
    row = next(s for c in teacher for t in c["tests"] for s in t["students"] if s["email"] == KID)
    assert row["forecast"]["grade"] == after_test


def test_no_test_means_no_forecast(world):
    client, store, lessons = world
    assert client.get("/api/forecast", headers=auth(KID)).json() == {"test": None, "forecast": None}
