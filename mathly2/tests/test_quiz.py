"""Drawing a lesson quiz (add-lesson-quizzes 1.3)."""
import random
from collections import Counter

import pytest

from mathly2 import quiz
from mathly2.bank import load_bank


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def lesson_with(bank, n):
    counts = Counter(s["unit"] for s in bank.skills if bank.question_keys(s["id"]))
    return next(l for l, c in counts.items() if c == n)


def per_skill(drawn):
    return Counter(q["skill_id"] for q in drawn)


def test_a_lesson_of_four_skills_gives_ten_questions_with_every_skill_at_least_two(bank):
    drawn = quiz.draw(bank, lesson_with(bank, 4), rng=random.Random(1))
    assert len(drawn) == 10 and len({q["key"] for q in drawn}) == 10
    assert sorted(per_skill(drawn).values()) == [2, 2, 3, 3]


def test_six_skills_give_quotas_2_2_2_2_1_1_and_two_skills_give_5_and_5(bank):
    assert sorted(per_skill(quiz.draw(bank, lesson_with(bank, 6), rng=random.Random(2))).values()) == [1, 1, 2, 2, 2, 2]
    assert sorted(per_skill(quiz.draw(bank, lesson_with(bank, 2), rng=random.Random(3))).values()) == [5, 5]


def test_every_skill_is_in_the_quiz_whatever_the_rng(bank):
    for lesson in {s["unit"] for s in bank.skills}:
        skills = {s["id"] for s in bank.skills if s["unit"] == lesson and bank.question_keys(s["id"])}
        for seed in range(5):
            assert set(per_skill(quiz.draw(bank, lesson, rng=random.Random(seed)))) == skills


def test_a_skill_without_questions_is_left_out_and_the_others_still_give_ten(bank):
    lesson = next(s["unit"] for s in bank.skills if not bank.question_keys(s["id"]))
    drawn = quiz.draw(bank, lesson, rng=random.Random(4))
    empty = {s["id"] for s in bank.skills if not bank.question_keys(s["id"])}
    assert len(drawn) == 10 and not empty & set(per_skill(drawn))


def test_a_retake_uses_new_questions_while_enough_remain_and_then_the_least_used(bank):
    lesson = lesson_with(bank, 4)
    used: Counter = Counter()
    first = quiz.draw(bank, lesson, used, random.Random(5))
    used.update(q["key"] for q in first)
    second = quiz.draw(bank, lesson, used, random.Random(6))
    used.update(q["key"] for q in second)
    assert not {q["key"] for q in first} & {q["key"] for q in second}                     # two in a row never repeat
    third = quiz.draw(bank, lesson, used, random.Random(7))
    assert not {q["key"] for q in first + second} & {q["key"] for q in third} or all(used[q["key"]] == 1 for q in third)
    assert max(used[q["key"]] for q in third) <= 1                                         # repeats come from the least-used ones
    for _ in range(12):                                                                    # many retakes: nothing is drawn far more than the rest
        batch = quiz.draw(bank, lesson, used, random.Random())
        used.update(q["key"] for q in batch)
    pool = [k for s in bank.skills if s["unit"] == lesson for k in bank.question_keys(s["id"])]
    counts = [used[k] for k in pool]
    assert max(counts) - min(counts) <= 2


def test_the_same_rng_gives_the_same_quiz_and_a_small_pool_gives_what_there_is(bank):
    lesson = lesson_with(bank, 3)
    assert quiz.draw(bank, lesson, rng=random.Random(9)) == quiz.draw(bank, lesson, rng=random.Random(9))
    assert len(quiz.draw(bank, lesson, rng=random.Random(9), size=4)) == 4
    assert quiz.draw(bank, "no-such-lesson") == []
