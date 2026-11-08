"""The attempt engine (add-lesson-quizzes 1.2): grades, settling, and what a result reveals."""
import copy
import json
from datetime import datetime, timedelta, timezone

import pytest

from mathly2 import attempts
from mathly2.bank import Bank, load_bank, question_key
from mathly2.store import InMemoryStore

U = "11111111-1111-1111-1111-111111111111"
T0 = datetime(2026, 11, 10, 9, 0, tzinfo=timezone.utc)
DUE = T0 + timedelta(minutes=15)


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def refs(bank, n=4):
    """n questions from the first skills that have enough: [{skill_id, key}]."""
    out = []
    for skill in bank.skills:
        for q in skill.get("questions", [])[:2]:
            out.append({"skill_id": skill["id"], "key": question_key(skill["id"], q)})
    return out[:n]


def choose(bank, ref, right=True):
    question = bank._questions[ref["skill_id"]][ref["key"]]
    picks = [i for i, c in enumerate(question["choices"]) if bool(c.get("correct")) == right]
    if not right:
        picks = [i for i in picks if question["choices"][i].get("mistake")] or picks
    return picks[0]


def make(bank, n=4, **answers):
    store = InMemoryStore()
    questions = refs(bank, n)
    row = store.create_attempt(U, "quiz", "t", T0, DUE, questions)
    return store, row, questions


def test_the_grade_is_the_rounded_share_of_right_answers():
    assert attempts.percent(7, 10) == 70 and attempts.percent(8, 12) == 67 and attempts.percent(0, 10) == 0 and attempts.percent(10, 10) == 100
    assert attempts.percent(1, 8) == 13 and attempts.percent(1, 3) == 33 and attempts.percent(2, 3) == 67 and attempts.percent(0, 0) == 0


def test_an_unanswered_or_unknown_answer_counts_as_wrong(bank):
    store, row, questions = make(bank, 4)
    answers = {questions[0]["key"]: choose(bank, questions[0]), questions[1]["key"]: 99, questions[2]["key"]: "x"}
    assert attempts.grade(bank, questions, answers) == (25, 1)
    assert attempts.grade(bank, questions, {}) == (0, 0)


def test_settling_grades_from_the_answers_saved_and_marks_timed_out(bank):
    store, row, questions = make(bank, 4)
    store.save_attempt(row["id"], answers={q["key"]: choose(bank, q) for q in questions[:3]})
    before = attempts.settle(store, bank, store.get_attempt(row["id"]), DUE - timedelta(seconds=1))
    assert before["submitted_at"] is None and before["grade"] is None                     # not overdue: untouched
    settled = attempts.settle(store, bank, store.get_attempt(row["id"]), DUE + timedelta(minutes=20))
    assert settled["grade"] == 75 and settled["timed_out"] is True and settled["submitted_at"] == DUE
    again = attempts.settle(store, bank, settled, DUE + timedelta(hours=5))
    assert again == settled == store.get_attempt(row["id"])                               # settling twice changes nothing


def test_submitting_before_the_deadline_grades_at_once_and_is_idempotent(bank):
    store, row, questions = make(bank, 4)
    store.save_attempt(row["id"], answers={q["key"]: choose(bank, q) for q in questions[:2]})
    done = attempts.submit(store, bank, store.get_attempt(row["id"]), T0 + timedelta(minutes=5))
    assert done["grade"] == 50 and done["timed_out"] is False and done["submitted_at"] == T0 + timedelta(minutes=5)
    store.save_attempt(row["id"], answers={q["key"]: choose(bank, q) for q in questions})   # even if answers changed afterwards...
    assert attempts.submit(store, bank, store.get_attempt(row["id"]), T0 + timedelta(minutes=6))["grade"] == 50   # ...the grade stands


def test_submitting_after_the_deadline_is_a_timeout(bank):
    store, row, questions = make(bank, 4)
    done = attempts.submit(store, bank, row, DUE + timedelta(minutes=1))
    assert done["timed_out"] is True and done["grade"] == 0


def test_the_result_lists_lost_skills_and_mistakes_but_never_the_right_answer(bank):
    store, row, questions = make(bank, 4)
    answers = {questions[0]["key"]: choose(bank, questions[0]),                            # right
               questions[1]["key"]: choose(bank, questions[1], right=False),               # wrong, with a named mistake
               questions[2]["key"]: choose(bank, questions[2], right=False)}               # wrong; the fourth is not answered
    store.save_attempt(row["id"], answers=answers)
    done = attempts.submit(store, bank, store.get_attempt(row["id"]), T0 + timedelta(minutes=3))
    out = attempts.result(bank, done)
    assert out["grade"] == 25 and out["right"] == 1 and out["total"] == 4 and len(out["missed"]) == 3
    assert {s["id"] for s in out["lost_skills"]} == {q["skill_id"] for q in questions[1:]}
    assert sum(s["missed"] for s in out["lost_skills"]) == 3
    unanswered = out["missed"][-1]
    assert unanswered["picked"] is None and unanswered["mistake"] is None
    wrong = out["missed"][0]
    assert wrong["picked"] and wrong["question"] and wrong["skill_name"]
    blob = json.dumps(out, ensure_ascii=False)
    assert '"correct"' not in blob
    for ref in questions[1:]:                                                              # no right choice's text appears
        question = bank._questions[ref["skill_id"]][ref["key"]]
        right_text = next(c["text"] for c in question["choices"] if c.get("correct"))
        picked_texts = {m["picked"] for m in out["missed"]}
        assert right_text not in picked_texts or right_text == wrong["picked"]


def test_a_question_the_bank_no_longer_has_is_skipped_in_the_result(bank):
    store, row, questions = make(bank, 3)
    data = copy.deepcopy(bank.data)
    gone = questions[0]
    for s in data["skills"]:
        if s["id"] == gone["skill_id"]:
            s["questions"] = [q for q in s["questions"] if question_key(s["id"], q) != gone["key"]]
    smaller = Bank(data)
    done = attempts.submit(store, smaller, store.get_attempt(row["id"]), T0 + timedelta(minutes=1))
    out = attempts.result(smaller, done)
    assert out["total"] == 3 and len(out["missed"]) == 2                                   # the vanished question is not listed
