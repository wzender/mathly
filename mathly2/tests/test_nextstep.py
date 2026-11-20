"""Home's next step (nextstep.py): one exercise and why, in priority order."""
from datetime import date, timedelta

from mathly2 import nextstep
from mathly2.bank import load_bank

BANK = load_bank()
TODAY = date(2026, 11, 20)
L1, L2 = BANK.lessons[0]["id"], BANK.lessons[1]["id"]
S1 = [s["id"] for s in BANK.skills if s["unit"] == L1]
S2 = [s["id"] for s in BANK.skills if s["unit"] == L2]


def lessons(**marks):
    return [{"id": L1, "name": "א", "stars": 0, "behind": False, "due_date": None, "round_open": False, **marks.get(L1, {})},
            {"id": L2, "name": "ב", "stars": 1, "behind": False, "due_date": None, "round_open": False, **marks.get(L2, {})}]


def answer(skill, right, day, counted=True):
    return {"skill_id": skill, "correct": right, "counted": counted, "day": day}


def choose(rows=None, recent=(), test=None, facts=None, answers=None, daily=None, states=None):
    return nextstep.choose(bank=BANK, lessons=rows or lessons(), next_lesson=L1, states=states or {}, recent=list(recent), today=TODAY,
                           daily=daily or {"done": 0, "goal": 5}, test=test, test_facts=facts, test_answers=answers or {})


def test_one_answer_from_a_crown_needs_two_right_and_another_day():
    yesterday = TODAY - timedelta(days=1)
    assert nextstep.one_answer_from_crown([answer("a", True, yesterday), answer("a", True, yesterday)], TODAY) == ["a"]
    assert nextstep.one_answer_from_crown([answer("a", True, TODAY), answer("a", True, TODAY)], TODAY) == []          # today only: not yet
    assert nextstep.one_answer_from_crown([answer("a", True, yesterday), answer("a", False, yesterday)], TODAY) == []
    assert nextstep.one_answer_from_crown([answer("a", True, yesterday, counted=False), answer("a", True, yesterday)], TODAY) == []


def test_an_open_round_comes_first_then_a_crown_then_a_lesson_behind():
    yesterday = TODAY - timedelta(days=1)
    crown = [answer(S2[0], True, yesterday), answer(S2[0], True, yesterday)]
    assert choose(lessons(**{L2: {"round_open": True}}), crown)["kind"] == "continue"
    got = choose(lessons(**{L1: {"behind": True, "due_date": "2026-11-10"}}), crown)
    assert got["kind"] == "crown" and got["skill"]["id"] == S2[0] and got["href"] == f"#/skill/{S2[0]}" and got["questions"] == 1
    behind = choose(lessons(**{L2: {"behind": True, "due_date": "2026-11-10"}}))
    assert behind["kind"] == "behind" and behind["lesson"]["id"] == L2 and behind["href"] == f"#/round/{L2}"


def test_a_close_test_points_at_its_weakest_lesson_and_a_far_one_at_the_biggest_gain():
    facts = {"covered": S1 + S2, "states": {s: "mastered" for s in S1}}
    close = choose(test={"days_left": 5, "date": "2026-11-25", "questions": 12}, facts=facts)
    assert close["kind"] == "test" and close["lesson"]["id"] == L2 and close["in_test"] == round(12 * len(S2) / len(S1 + S2))
    far = choose(test={"days_left": 40, "date": "2026-12-30", "questions": 12}, facts=facts)
    assert far["kind"] == "league" and far["lesson"]["id"] == L2 and far["gain"] > 0               # the unmastered lesson moves it most


def test_with_nothing_else_the_next_lesson_and_the_daily_goal_is_marked():
    got = choose(daily={"done": 3, "goal": 5})
    assert got["kind"] == "next" and got["lesson"]["id"] == L1 and got["completes_goal"] is True and got["minutes"] == 5
    assert choose(daily={"done": 5, "goal": 5})["completes_goal"] is False
