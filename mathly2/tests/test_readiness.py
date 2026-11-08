"""The readiness number (add-test-readiness 1.3)."""
import pytest

from mathly2 import readiness


def test_only_mastery_so_far_gives_that_percent():
    got = readiness.compute(60, None, None)
    assert got["number"] == 60 and got["capped"] is False and got["parts"] == {"M": 60, "E": None, "S": None}


def test_all_three_parts_are_weighted_50_20_30():
    assert readiness.compute(80, 70, 90)["number"] == 81
    assert readiness.compute(100, 100, 100)["number"] == 100 and readiness.compute(0, 0, 0)["number"] == 0


def test_a_missing_part_is_left_out_and_the_others_are_scaled_up():
    assert readiness.compute(80, 60, None)["number"] == 74           # (50*80 + 20*60) / 70, rounded
    assert readiness.compute(50, None, 70)["number"] == 58           # (50*50 + 30*70) / 80
    assert readiness.compute(None, None, 40)["number"] == 40


def test_before_the_simulation_the_number_is_capped_at_80_and_says_so():
    got = readiness.compute(100, 95, None)
    assert got["number"] == 80 and got["capped"] is True and got["waiting_for_simulation"] is True
    assert readiness.compute(100, 95, 100)["number"] == 99 and readiness.compute(100, 95, 100)["waiting_for_simulation"] is False
    assert readiness.compute(79, None, None)["capped"] is False


def test_labels_at_their_edges():
    for number, name in ((0, "מתחילים"), (39, "מתחילים"), (40, "בדרך"), (69, "בדרך"), (70, "כמעט שם"), (84, "כמעט שם"), (85, "מוכנים"), (100, "מוכנים")):
        assert readiness.label(number) == name


@pytest.mark.parametrize("m,e", [(100, 100), (100, 0), (90, 95), (85, 85)])
def test_ready_never_shows_without_the_simulation(m, e):
    assert readiness.compute(m, e, None)["label"] != "מוכנים"
    assert readiness.compute(100, 100, 100)["label"] == "מוכנים"


def test_nothing_known_is_zero_and_the_parts_helpers():
    assert readiness.compute(None, None, None)["number"] == 0
    assert readiness.mastery_percent(3, 4) == 75 and readiness.mastery_percent(0, 0) is None
    assert readiness.exercise_average([60, 80]) == 70 and readiness.exercise_average([]) is None
