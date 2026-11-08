import random
from datetime import date, timedelta

import pytest

from mathly2.learning import (LEARNING, MASTERED, NOT_STARTED, current_round, is_mastered, mark_started, next_in_round, next_skill,
                              record_practice_answer, skill_state, streak, today_progress)
from mathly2.store import InMemoryStore

U, S = "u-1", "skill-1"
MON, TUE = date(2026, 11, 2), date(2026, 11, 3)
NOW = "2026-11-02T10:00:00+00:00"


@pytest.fixture
def store():
    return InMemoryStore()


def answer(store, n, correct, day, counted=True):
    return record_practice_answer(store, U, S, f"{S}:q{n}", correct, counted, None if correct else "m1", day, NOW)


def state(store):
    return skill_state(store.get_progress(U, S))


# --- the mastery rule (spec: skill-mastery) ---

def test_mastered_over_two_days(store):
    answer(store, 1, True, MON)
    answer(store, 2, True, MON)
    assert state(store) == LEARNING
    answer(store, 3, True, TUE)
    assert state(store) == MASTERED


def test_three_in_a_row_on_one_day_is_not_yet_mastered(store):
    for n in (1, 2, 3):
        answer(store, n, True, MON)
    assert state(store) == LEARNING
    answer(store, 4, True, TUE)           # the last 3 are now Mon, Mon, Tue
    assert state(store) == MASTERED


def test_help_opened_skips_the_answer_without_breaking_the_run(store):
    answer(store, 1, True, MON)
    answer(store, 2, True, MON)
    answer(store, 3, True, MON, counted=False)       # helped: ignored for mastery
    assert state(store) == LEARNING                   # a helped answer cannot be the third
    answer(store, 4, True, TUE)
    assert state(store) == MASTERED                   # Mon, Mon, Tue: the run survived the helped answer


def test_a_wrong_answer_restarts_the_run(store):
    answer(store, 1, True, MON)
    answer(store, 2, True, MON)
    answer(store, 3, False, MON)
    answer(store, 4, True, TUE)
    assert state(store) == LEARNING                   # the last 3 are correct, wrong, correct
    answer(store, 5, True, TUE)
    answer(store, 6, True, TUE + timedelta(days=1))
    assert state(store) == MASTERED


def test_a_wrong_answer_months_later_does_not_undo_mastery(store):
    answer(store, 1, True, MON)
    answer(store, 2, True, MON)
    answer(store, 3, True, TUE)
    first = store.get_progress(U, S)["mastered_at"]
    answer(store, 4, False, date(2027, 3, 8))
    assert state(store) == MASTERED
    assert store.get_progress(U, S)["mastered_at"] == first


def test_mastered_at_is_set_once(store):
    answer(store, 1, True, MON)
    answer(store, 2, True, MON)
    record_practice_answer(store, U, S, "k3", True, True, None, TUE, "2026-11-03T08:00:00+00:00")
    record_practice_answer(store, U, S, "k4", True, True, None, TUE, "2026-11-09T08:00:00+00:00")
    assert store.get_progress(U, S)["mastered_at"] == "2026-11-03T08:00:00+00:00"


def test_is_mastered_needs_exactly_the_last_three():
    a = lambda correct, day: {"correct": correct, "day": day}
    assert not is_mastered([])
    assert not is_mastered([a(True, MON), a(True, TUE)])
    assert is_mastered([a(False, MON), a(True, MON), a(True, MON), a(True, TUE)])


# --- skill states ---

def test_skill_states(store):
    assert skill_state(None) == NOT_STARTED
    assert state(store) == NOT_STARTED
    store.save_progress(U, S, current_key="k")           # a row without started_at is still not started
    assert state(store) == NOT_STARTED


def test_a_why_answer_moves_a_skill_to_learning_but_cannot_master_it(store):
    mark_started(store, U, S, NOW)
    assert state(store) == LEARNING
    for _ in range(5):
        mark_started(store, U, S, NOW)
    assert state(store) == LEARNING                   # only practice answers can master
    assert store.get_progress(U, S)["started_at"] == NOW


def test_first_practice_answer_moves_not_started_to_learning(store):
    answer(store, 1, False, MON)
    assert state(store) == LEARNING


# --- the round: each question of a skill once ---

KEYS = [f"k{i}" for i in range(10)]


def rows(*pairs):
    return [{"question_key": k, "correct": ok, "counted": True, "day": MON, "mistake_id": None} for k, ok in pairs]


def test_a_round_asks_every_question_once_and_ends_when_all_are_answered():
    rng, answered, last, shown = random.Random(1), [], None, []
    left = list(KEYS)
    while True:
        nxt = next_in_round(left, last, rng)
        if nxt is None:
            break
        shown.append(nxt)
        answered.append((nxt, len(shown) % 3 != 0))                  # every third answer wrong
        last = nxt
        left = current_round(KEYS, rows(*answered), 0)["left"]
    assert sorted(shown) == sorted(KEYS) and len(set(shown)) == 10      # each once, a wrong one does not come back
    assert current_round(KEYS, rows(*answered), 0)["done"] is True


def test_the_round_is_the_answers_since_its_start_and_no_start_means_a_new_round_begins():
    old = rows(("k0", True), ("k1", False), ("k2", True))
    assert current_round(KEYS, old, None) == {"answers": [], "left": KEYS, "done": False}        # an old student: everything so far is past
    now = old + rows(("k5", True), ("k6", False))
    got = current_round(KEYS, now, 3)
    assert [a["question_key"] for a in got["answers"]] == ["k5", "k6"] and got["left"] == [k for k in KEYS if k not in ("k5", "k6")] and not got["done"]


def test_a_question_not_in_the_round_or_repeated_is_ignored_and_a_skill_with_no_questions_is_never_done():
    got = current_round(["a", "b"], rows(("a", True), ("a", False), ("zzz", True)), 0)
    assert [a["question_key"] for a in got["answers"]] == ["a"] and got["left"] == ["b"] and not got["done"]
    assert current_round([], [], 0)["done"] is False


def test_next_in_round_is_never_the_one_just_answered_and_none_when_nothing_is_left():
    rng = random.Random(2)
    for _ in range(50):
        assert next_in_round(["k1", "k2", "k3"], "k2", rng) != "k2"
    assert next_in_round([]) is None and next_in_round(["k1"], "k1") is None
    assert next_in_round(["only"]) == "only"                          # a skill with one question: a round of one


# --- daily goal and streak ---

TODAY = date(2026, 11, 10)


def test_goal_missed_and_reached():
    assert today_progress({TODAY: 3}, TODAY) == {"done": 3, "goal": 5, "reached": False}
    assert today_progress({TODAY: 5}, TODAY)["reached"] is True
    assert today_progress({}, TODAY)["done"] == 0


def test_streak_counts_today_once_it_reaches_five():
    assert streak({TODAY: 5, TODAY - timedelta(days=1): 6}, TODAY) == 2


def test_streak_is_kept_before_todays_five():
    daily = {TODAY: 3, TODAY - timedelta(days=1): 5, TODAY - timedelta(days=2): 7}
    assert streak(daily, TODAY) == 2


def test_streak_breaks_after_a_missed_day():
    daily = {TODAY: 5, TODAY - timedelta(days=1): 4, TODAY - timedelta(days=2): 9}
    assert streak(daily, TODAY) == 1
    assert streak({TODAY - timedelta(days=2): 9}, TODAY) == 0
    assert streak({}, TODAY) == 0


# --- the next skill (add-learning-core 1.4; spec: Next skill) ---

ORDER = ["a", "b", "c", "d"]


def test_a_new_student_gets_the_first_skill():
    assert next_skill(ORDER, {}, []) == "a"


def test_the_marker_stays_on_the_skill_answered_last_while_it_is_not_mastered():
    states = {"a": MASTERED, "b": LEARNING, "c": LEARNING}
    assert next_skill(ORDER, states, ["c", "b", "a"]) == "c"                    # c was answered most recently


def test_when_the_last_answer_mastered_a_skill_it_goes_to_the_most_recent_unmastered_one():
    states = {"a": MASTERED, "b": LEARNING, "c": MASTERED}
    assert next_skill(ORDER, states, ["c", "b", "a"]) == "b"


def test_when_every_recent_skill_is_mastered_it_goes_to_the_first_unmastered_in_order():
    states = {"c": MASTERED, "d": MASTERED}
    assert next_skill(ORDER, states, ["d", "c"]) == "a"


def test_when_everything_is_mastered_nothing_is_marked():
    assert next_skill(ORDER, {k: MASTERED for k in ORDER}, ["a", "b"]) is None


def test_skills_outside_the_students_lessons_never_carry_the_marker():
    assert next_skill(ORDER, {}, ["elsewhere", "b"]) == "b"
    assert next_skill([], {}, ["a"]) is None


def test_the_marker_never_changes_the_states_or_the_order():
    states, order = {"a": LEARNING}, list(ORDER)
    next_skill(order, states, ["a"])
    assert states == {"a": LEARNING} and order == ORDER
