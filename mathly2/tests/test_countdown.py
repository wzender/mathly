"""The countdown plan and today's task (add-test-readiness 1.2)."""
from datetime import date, timedelta

from mathly2 import countdown as c

TEST = date(2026, 11, 30)
SET_LONG = TEST - timedelta(days=14)


def facts(**kw):
    base = {"path_done": False, "next_path_skill": "s1", "ex1_done": False, "ex2_done": False, "sim_taken": False,
            "review_left": [], "stale": ["old", "older"]}
    return {**base, **kw}


def on(days_left, plan_for=SET_LONG, **kw):
    return c.task(days_left, c.plan(TEST, plan_for), facts(**kw))


def test_the_plan_for_two_weeks_has_the_prds_days():
    assert c.plan(TEST, SET_LONG) == {"n": 14, "ex1": 9, "ex2": 7, "sim": 5, "review_from": 4}
    assert c.plan(TEST, TEST - timedelta(days=9))["ex1"] == 9


def test_twelve_days_ahead_the_plan_asks_to_finish_the_path():
    assert on(12) == {"kind": "path", "skill": "s1"}
    assert on(10) == {"kind": "path", "skill": "s1"}


def test_nine_seven_and_five_days_ahead_are_exercise_test_1_2_and_the_simulation():
    assert on(9, path_done=True) == {"kind": "ex1"}
    assert on(8, path_done=True) == {"kind": "ex1"}
    assert on(7, path_done=True, ex1_done=True) == {"kind": "ex2"}
    assert on(5, path_done=True, ex1_done=True, ex2_done=True) == {"kind": "sim"}


def test_the_recommended_step_comes_first_even_when_an_earlier_one_was_missed():
    assert on(5) == {"kind": "sim"}                                  # exercise tests missed: the required simulation still comes first
    assert on(7) == {"kind": "ex2"}


def test_a_done_step_moves_to_the_next_one_early_but_never_to_a_closed_simulation():
    assert on(12, path_done=True) == {"kind": "ex1"}                 # the path is done: exercise test 1 early
    assert on(12, path_done=True, ex1_done=True) == {"kind": "ex2"}
    assert on(10, path_done=True, ex1_done=True, ex2_done=True) == {"kind": "continue"}   # the simulation is not open yet
    assert on(9, path_done=False, ex1_done=True) == {"kind": "ex2"}


def test_after_the_simulation_the_last_days_review_a_failed_skill_and_the_day_before_is_mixed():
    done = dict(path_done=True, ex1_done=True, ex2_done=True, sim_taken=True)
    assert on(3, review_left=["f1", "f2"], **done) == {"kind": "review", "skill": "f1"}
    assert on(2, review_left=["f2"], **done) == {"kind": "review", "skill": "f2"}
    assert on(4, review_left=[], **done) == {"kind": "mixed_review", "skill": "old"}     # nothing failed is left: mixed review
    assert on(1, review_left=["f2"], **done) == {"kind": "mixed_review", "skill": "old"}  # the day before is always the light mixed review
    assert on(0, review_left=["f2"], **done) == {"kind": "continue"}


def test_the_simulation_is_asked_for_in_the_last_days_if_it_was_not_taken():
    assert on(4, path_done=True, ex1_done=True, ex2_done=True) == {"kind": "sim"}
    assert on(0) == {"kind": "sim"}                                  # open until the test day


def test_a_test_set_six_days_ahead_keeps_the_order_within_six_days():
    p = c.plan(TEST, TEST - timedelta(days=6))
    assert p == {"n": 6, "ex1": 6, "ex2": 5, "sim": 3, "review_from": 3}
    days = [p["ex1"], p["ex2"], p["sim"]]
    assert days == sorted(days, reverse=True) and p["ex1"] <= 6
    sequence = [c.step_for(d, p) for d in range(6, 0, -1)]
    assert sequence == ["ex1", "ex2", "ex2", "sim", "sim", "sim"]    # path, then ex1, ex2, simulation, then review (after the simulation)
    after = {**facts(path_done=True, ex1_done=True, ex2_done=True, sim_taken=True, review_left=["f"])}
    assert c.task(2, p, after) == {"kind": "review", "skill": "f"}


def test_a_very_short_notice_keeps_every_step_startable_in_order():
    p = c.plan(TEST, TEST - timedelta(days=2))
    assert p["ex1"] >= p["ex2"] >= p["sim"] >= p["review_from"] >= 1
    assert c.task(2, p, facts(path_done=True)) == {"kind": "ex1"}
    assert c.task(2, p, facts(path_done=True, ex1_done=True)) == {"kind": "ex2"}


def test_the_closest_test_gives_the_task():
    soon = {"id": 1, "date": date(2026, 11, 14)}
    later = {"id": 2, "date": date(2026, 11, 20)}
    today = date(2026, 11, 10)
    assert c.closest([later, soon], today)["id"] == 1                # tests in 4 and in 10 days: the one in 4
    assert c.closest([{"id": 3, "date": date(2026, 11, 9)}], today) is None
    assert c.closest([{"id": 4, "date": today}], today)["id"] == 4   # the test day itself is still upcoming
    assert c.closest([], today) is None


def test_the_outline_lists_the_steps_with_their_days_and_done_marks():
    p = c.plan(TEST, SET_LONG)
    steps = c.outline(p, facts(path_done=True, ex1_done=True, sim_taken=True, review_left=["x"]))
    assert [(s["id"], s["done"]) for s in steps] == [("path", True), ("ex1", True), ("ex2", False), ("sim", True), ("review", False)]
    assert [s["day"] for s in steps[1:]] == [9, 7, 5, 4]
