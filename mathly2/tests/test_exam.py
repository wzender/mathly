"""Drawing exercise tests and simulations (add-test-readiness 1.4)."""
import random
from collections import Counter

import pytest

from mathly2 import exam
from mathly2.bank import load_bank


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def lessons_and_skills(bank, count=2, per=4):
    """Lessons whose skills all have questions, enough skills in total: (lessons, skill ids)."""
    sizes = Counter(s["unit"] for s in bank.skills if bank.question_keys(s["id"]))
    lessons = [l for l, c in sizes.items() if c == per][:count]
    return lessons, [s["id"] for s in bank.skills if s["unit"] in lessons]


def states(skills, learning=(), mastered=(), **kw):
    out = {i: "not_started" for i in skills}
    out.update({i: "learning" for i in learning})
    out.update({i: "mastered" for i in mastered})
    return out


def per_skill(drawn):
    return Counter(q["skill_id"] for q in drawn["questions"])


def test_few_weak_skills_give_one_question_each_and_the_rest_comes_from_other_skills(bank):
    lessons, skills = lessons_and_skills(bank)               # 8 skills
    weak = skills[:3]
    got = exam.draw(bank, lessons, states(skills, learning=weak, mastered=skills[3:]), 12, share=0.6, rng=random.Random(1))
    assert len(got["questions"]) == 12 and got["weak"] == weak
    counts = per_skill(got)
    assert sum(counts[i] for i in weak) == 3                  # 7 weak needed, only 3 weak skills: 3 weak questions
    assert sum(counts[i] for i in skills[3:]) == 9            # the other 9 from other covered skills


def test_enough_weak_skills_give_60_percent_in_test_1_and_30_in_test_2(bank):
    lessons, skills = lessons_and_skills(bank, count=3)      # 12 skills
    weak, others = skills[:9], skills[9:]
    st = states(skills, learning=weak, mastered=others)
    one = exam.draw(bank, lessons, st, 10, share=exam.EXERCISE_SHARE[1], rng=random.Random(2))
    two = exam.draw(bank, lessons, st, 10, share=exam.EXERCISE_SHARE[2], rng=random.Random(3))
    # the other skills are then drawn from round after round; the weak ones come first, one per skill
    assert sum(per_skill(one)[i] for i in weak) >= 6 and sum(per_skill(two)[i] for i in weak) >= 3
    assert len(one["questions"]) == len(two["questions"]) == 10


def test_a_not_started_skill_is_never_drawn_and_is_listed_to_practise_first(bank):
    lessons, skills = lessons_and_skills(bank)
    st = states(skills, learning=skills[:2], mastered=skills[2:5])      # skills[5:] are not started
    got = exam.draw(bank, lessons, st, 12, share=0.6, rng=random.Random(4))
    assert got["practice_first"] == skills[5:]
    assert not set(per_skill(got)) & set(skills[5:])


def test_include_unstarted_draws_the_not_started_skills_too(bank):
    lessons, skills = lessons_and_skills(bank)
    got = exam.draw(bank, lessons, states(skills), 12, share=0.6, include_unstarted=True, rng=random.Random(11))
    assert len(got["questions"]) == 12 and got["practice_first"] == skills


def test_a_skill_answered_wrong_in_an_earlier_exercise_test_counts_as_weak(bank):
    lessons, skills = lessons_and_skills(bank)
    st = states(skills, mastered=skills)                       # everything mastered: nothing weak by state
    got = exam.draw(bank, lessons, st, 12, share=0.6, weak_before={skills[0], skills[1]}, rng=random.Random(5))
    assert set(got["weak"]) == {skills[0], skills[1]}
    assert per_skill(got)[skills[0]] >= 1 and per_skill(got)[skills[1]] >= 1


def test_a_retake_takes_new_questions_while_enough_remain(bank):
    lessons, skills = lessons_and_skills(bank)
    st = states(skills, learning=skills)
    used: Counter = Counter()
    first = exam.draw(bank, lessons, st, 12, share=0.6, used=used, rng=random.Random(6))
    used.update(q["key"] for q in first["questions"])
    second = exam.draw(bank, lessons, st, 12, share=0.6, used=used, rng=random.Random(7))
    assert not {q["key"] for q in first["questions"]} & {q["key"] for q in second["questions"]}


def test_the_simulation_spreads_one_question_per_skill_round_after_round(bank):
    lessons, skills = lessons_and_skills(bank)               # 8 skills
    st = states(skills, learning=skills[:2], mastered=skills[2:])
    got = exam.draw(bank, lessons, st, 12, share=0.0, rng=random.Random(8))
    counts = per_skill(got)
    assert len(got["questions"]) == 12 and set(counts) == set(skills) and sorted(counts.values()) == [1, 1, 1, 1, 2, 2, 2, 2]
    assert len({q["key"] for q in got["questions"]}) == 12


def test_nothing_started_gives_no_questions_and_everything_is_listed(bank):
    lessons, skills = lessons_and_skills(bank)
    got = exam.draw(bank, lessons, states(skills), 12, share=0.6, rng=random.Random(9))
    assert got["questions"] == [] and got["practice_first"] == skills and got["weak"] == []


def test_a_small_pool_gives_what_there_is_and_the_draw_is_repeatable(bank):
    lessons, skills = lessons_and_skills(bank, count=1)
    st = states(skills, learning=skills[:1])
    few = exam.draw(bank, lessons, st, 40, share=0.6, rng=random.Random(10))
    assert len(few["questions"]) == len(bank.question_keys(skills[0]))                    # one started skill: its own questions only
    a = exam.draw(bank, lessons, states(skills, learning=skills), 12, share=0.6, rng=random.Random(11))
    b = exam.draw(bank, lessons, states(skills, learning=skills), 12, share=0.6, rng=random.Random(11))
    assert a == b
