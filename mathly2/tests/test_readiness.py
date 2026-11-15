"""The readiness number: deepening sets where it starts; tests move it only up, a simulation more than a practice test, a picked one less."""
from mathly2 import readiness


def test_nothing_taken_is_zero_and_a_good_test_pulls_it_toward_its_grade():
    assert readiness.compute([])["number"] == 0
    assert readiness.compute([("practice", 80)])["number"] == 24                     # 30% of the way to 80
    assert readiness.compute([("simulation", 80)])["number"] == 48                   # 60%: a simulation counts more
    assert readiness.compute([("manual", 80)])["number"] == 12                       # 15%: the student picked the skills


def test_a_grade_below_the_number_never_lowers_it_and_the_number_never_passes_the_grades():
    up = readiness.compute([("simulation", 90), ("simulation", 90)])["number"]
    assert up == 76 and readiness.compute([("simulation", 90), ("simulation", 90), ("practice", 30)])["number"] == up
    many = readiness.compute([("simulation", 90)] * 20)["number"]
    assert many == 90


def test_levels_next_level_and_what_a_perfect_test_would_add():
    r = readiness.compute([("practice", 100)])
    assert r["number"] == 30 and r["label"] == "מתחילים" and r["next"] == {"at": 40, "name": "בדרך", "left": 10}
    assert r["can_add"] == {"simulation": 42, "practice": 21, "manual": 11}
    assert readiness.compute([("simulation", 100)] * 5)["next"] is None
    assert r["practices"] == 1 and r["simulations"] == 0 and r["practice_best"] == 100 and r["simulation_best"] is None


def test_change_says_the_gain_and_a_new_level():
    moved = readiness.change([("practice", 100)], ("simulation", 90))
    assert moved == {**moved, "before": 30, "after": 66, "gain": 36, "label": "בדרך", "level_up": True}
    assert readiness.change([("simulation", 90)], ("practice", 20))["gain"] == 0


def test_deepening_is_the_start_and_tests_pull_from_there():
    assert readiness.compute([], 0.5)["number"] == 10                                # half the skills mastered: 20% of 50
    assert readiness.compute([], 1.0)["number"] == 20 and readiness.compute([], 1.0)["deepening"] == 20
    assert readiness.compute([("simulation", 80)], 0.5)["number"] == 52              # 10, then 60% of the way to 80
    assert readiness.compute([("simulation", 80)], 1.0)["can_add"]["simulation"] == 26   # at 56, a perfect simulation adds 60% of 44
    more = [readiness.compute([("practice", 70)], share)["number"] for share in (0, 0.25, 0.5, 1)]
    assert more == sorted(more) and more[0] < more[-1]                                # more mastery never lowers it
    assert readiness.change([], ("practice", 80), 1.0) == {**readiness.change([], ("practice", 80), 1.0), "before": 20, "after": 38, "gain": 18}
