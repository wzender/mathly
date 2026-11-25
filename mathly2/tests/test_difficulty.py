"""Question difficulty (difficulty.py): every bank question has a level; practice goes from easy to hard; the practice tests take medium
and hard only, PRACTICE_HARD of them hard; the simulation 1.5 times as many hard ones."""
import random

import pytest

from mathly2 import difficulty, exam, rounds
from mathly2.bank import load_bank, question_key
from mathly2.difficulty import EASY, HARD, MEDIUM, level
from mathly2.learning import next_in_round


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def test_every_question_of_the_bank_has_a_level_and_every_skill_has_medium_or_hard_ones(bank):
    keys = {question_key(s["id"], q) for s in bank.skills for q in s.get("questions", [])}
    assert set(difficulty.levels()) == keys and set(difficulty.levels().values()) == {EASY, MEDIUM, HARD}
    assert all(any(level(k) >= MEDIUM for k in bank.question_keys(s["id"])) for s in bank.skills if bank.question_keys(s["id"]))
    assert level("not-in-the-bank") == MEDIUM                                                # a worksheet's question counts as medium


def test_a_skills_round_goes_from_easy_to_hard(bank):
    skill = next(s["id"] for s in bank.skills if {level(k) for k in bank.question_keys(s["id"])} == {EASY, MEDIUM, HARD})
    left, seen, rng = list(bank.practice_keys(skill)), [], random.Random(1)
    while left:
        key = next_in_round(left, rng=rng)
        seen.append(level(key))
        left.remove(key)
    assert seen == sorted(seen)


def test_a_lesson_round_goes_from_easy_to_hard(bank):
    lesson = bank.lessons[0]["id"]
    drawn = rounds.draw(bank, lesson, {}, rng=random.Random(2))
    assert [level(q["key"]) for q in drawn] == sorted(level(q["key"]) for q in drawn) and len(drawn) > 3


@pytest.mark.parametrize("share", [exam.PRACTICE_HARD, exam.SIMULATION_HARD])
def test_tests_have_no_easy_questions_and_their_share_of_hard_ones(bank, share):
    lessons = [l["id"] for l in bank.lessons][:4]
    total = hard = 0
    for seed in range(30):
        drawn = exam.draw(bank, lessons, {}, 15, include_unstarted=True, rng=random.Random(seed), hard_share=share)["questions"]
        assert len(drawn) == 15 and all(level(q["key"]) >= MEDIUM for q in drawn)
        total, hard = total + len(drawn), hard + sum(level(q["key"]) == HARD for q in drawn)
    assert abs(hard / total - share) <= 0.05


def test_the_simulation_has_one_and_a_half_times_the_hard_share():
    assert exam.SIMULATION_HARD == pytest.approx(exam.PRACTICE_HARD * 1.5)


def test_focus_tests_too_and_easy_ones_only_when_nothing_else_is_left(bank):
    skills = [s["id"] for s in bank.skills if bank.question_keys(s["id"])][:5]
    drawn = exam.draw_focus(bank, skills, n=15, rng=random.Random(4))
    assert all(level(q["key"]) >= MEDIUM for q in drawn)
    one = next(i for i in skills if any(level(k) == EASY for k in bank.question_keys(i)))
    keys = bank.question_keys(one)
    not_easy = sum(level(k) >= MEDIUM for k in keys)
    drawn = exam.draw_focus(bank, [one], n=not_easy + 1, rng=random.Random(5))           # one more than the medium and hard ones
    assert len(drawn) == not_easy + 1 and sum(level(q["key"]) == EASY for q in drawn) == 1   # the easy ones only to fill what is missing
