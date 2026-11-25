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


def test_home_carries_the_next_step_toward_the_tests_material(world):
    client, store, lessons = world
    set_test(client, lessons, days=30)
    step = client.get("/api/home", headers=auth(KID)).json()["next_step"]
    assert step["kind"] in ("league", "next") and step["href"].startswith("#/round/") and step["questions"] == 10 and step["test"] is True
    assert step["lesson"]["id"] in lessons


def test_the_way_up_picks_the_best_rounds_one_after_another():
    from mathly2 import forecast
    skills = ["a1", "a2", "b1", "b2"]
    states = {"a1": "mastered", "a2": "mastered", "b1": "learning", "b2": "not_started"}
    answers = {"b1": [(False, 1.0)] * 3}
    got = forecast.boost(skills, states, set(), answers, {"A": ["a1", "a2"], "B": ["b1", "b2"]})
    now = forecast.compute(skills, states, set(), answers)["grade"]
    assert got["gains"] and got["gains"][0] == max(forecast.gain_of_round(skills, states, set(), answers, g) for g in (["a1", "a2"], ["b1", "b2"]))
    assert got["grade"] == min(100, now + sum(got["gains"])) and len(got["gains"]) <= 3 and all(g > 0 for g in got["gains"])
    assert forecast.boost(skills, states, set(), answers, {}) == {"gains": [], "grade": now}


# --- the held grade: start high, keep it with the daily mission, meet the forecast by the test ---

def test_the_held_grade_starts_25_above_and_loses_a_quarter_of_the_lead_a_day_without_the_mission():
    from datetime import date, timedelta
    from mathly2 import forecast
    start, test = date(2026, 12, 1), date(2027, 1, 30)                 # far: the mission is one round (10 answers)
    day = lambda n: start + timedelta(days=n)
    assert forecast.held(60, start, test, start, {})["grade"] == 85
    idle = forecast.held(60, start, test, day(2), {})
    assert idle["grade"] == round(60 + 25 * 0.75 ** 2) and idle["need"] == 10 and not idle["safe"]
    kept = forecast.held(60, start, test, day(2), {day(0): 10, day(1): 12, day(2): 10})
    assert kept["grade"] == 85 and kept["safe"] and kept["done"] == 10                     # the mission each day keeps it
    assert idle["tomorrow"] == round(60 + 25 * 0.75 ** 3)                                  # what is lost without today's mission
    assert forecast.held(90, start, test, start, {})["grade"] == 100                     # never above 100
    assert forecast.held(70, start, test, day(30), {})["grade"] >= 70                    # never below the forecast


def test_the_held_grade_meets_the_forecast_by_the_test_and_the_mission_grows():
    from datetime import date, timedelta
    from mathly2 import forecast
    test = date(2026, 12, 31)
    every_day = {test - timedelta(days=n): 40 for n in range(40)}
    far = forecast.held(60, test - timedelta(days=30), test, test - timedelta(days=20), every_day)
    near = forecast.held(60, test - timedelta(days=30), test, test - timedelta(days=7), every_day)
    on_the_day = forecast.held(60, test - timedelta(days=30), test, test, every_day)
    assert far["grade"] == 85 and near["grade"] == round(60 + 25 * 7 / 14) and on_the_day["grade"] == 60
    assert [forecast.mission_rounds(d) for d in (20, 10, 5, 2, 0)] == [1, 1, 2, 3, 0]
    assert near["need"] == 20 and forecast.held(60, test - timedelta(days=30), test, test - timedelta(days=2), {})["need"] == 30
