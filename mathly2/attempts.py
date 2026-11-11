"""Graded attempts: the engine under lesson quizzes, exercise tests and the simulation.

Only the simulation is timed (TIMED_KINDS); a lesson quiz or an exercise test stays open until the student hands it in. Every attempt
still stores a due_at (the database requires one), but only a timed attempt is held to it.

An attempt is open until it is graded. The server settles an overdue timed attempt on the first read after its deadline, so there is no
background job and the answer is right even if nothing ran at the deadline. Nothing here ever says which choice was right."""
from __future__ import annotations

import logging
from datetime import datetime

log = logging.getLogger("mathly2.attempts")

QUIZ_SIZE = 15
MINUTES_PER_QUESTION = 3
QUIZ_MINUTES = MINUTES_PER_QUESTION * QUIZ_SIZE   # 45
PASS_RIGHT = 13                    # right answers out of QUIZ_SIZE that pass a lesson quiz
TIMED_KINDS = frozenset({"simulation"})   # the only attempts with a time limit


def percent(right: int, total: int) -> int:
    """The grade: the share of right answers as a whole number 0-100, rounded half up (7/10 -> 70, 8/12 -> 67)."""
    return 0 if total <= 0 else (200 * right + total) // (2 * total)


PASS_GRADE = percent(PASS_RIGHT, QUIZ_SIZE)    # 87: a quiz is passed with this grade or better


def _right(bank, question: dict, answers: dict) -> bool:
    choice = answers.get(question["key"])
    graded = bank.grade(question["skill_id"], question["key"], choice) if isinstance(choice, int) else None
    return bool(graded and graded["correct"])


def grade(bank, questions: list[dict], answers: dict) -> tuple[int, int]:
    """(grade, number right). A question without an answer, or with an answer the bank does not know, is wrong."""
    right = sum(1 for q in questions if _right(bank, q, answers))
    return percent(right, len(questions)), right


def add_wrong_to_review(store, bank, row: dict, at: datetime) -> None:
    """Every question of a submitted attempt that was answered wrongly, or not answered, goes to the student's review list (חזרה). Recording it
    never fails the submit: a problem here is logged and the grade stands."""
    wrong = [(q["skill_id"], q["key"], row["kind"]) for q in row["questions"] if not _right(bank, q, row["answers"])]
    if not wrong:
        return
    try:
        store.add_review(row["user_id"], wrong, at)
    except Exception as exc:
        log.warning("could not add wrong answers to the review list: %s", type(exc).__name__)


def is_open(row: dict) -> bool:
    return row["submitted_at"] is None


def is_timed(row: dict) -> bool:
    return row["kind"] in TIMED_KINDS


def is_overdue(row: dict, now: datetime) -> bool:
    return is_open(row) and is_timed(row) and now >= row["due_at"]


def settle(store, bank, row: dict, now: datetime) -> dict:
    """Grade an overdue open attempt from the answers saved so far. Anything else is returned as it is."""
    if not is_overdue(row, now):
        return row
    value, _ = grade(bank, row["questions"], row["answers"])
    saved = store.save_attempt(row["id"], submitted_at=row["due_at"], timed_out=True, grade=value)
    add_wrong_to_review(store, bank, saved, row["due_at"])
    return saved


def submit(store, bank, row: dict, now: datetime) -> dict:
    """The student hands in. Idempotent: a submitted attempt is returned unchanged; a timed attempt (the simulation) past its deadline
    is settled as timed out. An untimed one is graded now, however late."""
    if not is_open(row):
        return row
    if is_overdue(row, now):
        return settle(store, bank, row, now)
    value, _ = grade(bank, row["questions"], row["answers"])
    saved = store.save_attempt(row["id"], submitted_at=now, timed_out=False, grade=value)
    add_wrong_to_review(store, bank, saved, now)
    return saved


def result(bank, row: dict) -> dict:
    """What the student sees after a submitted attempt: the grade, the skills that lost points and, for each missed question, the
    mistake's name and tip. It never carries a `correct` flag, the right choice or its position. A question the bank no longer has is skipped."""
    lost: dict[str, dict] = {}
    missed = []
    for q in row["questions"]:
        skill = bank.skill(q["skill_id"])
        served = bank.practice_question(q["skill_id"], q["key"])
        if skill is None or served is None or _right(bank, q, row["answers"]):
            continue
        choice = row["answers"].get(q["key"])
        graded = bank.grade(q["skill_id"], q["key"], choice) if isinstance(choice, int) else None
        mistake = graded["mistake"] if graded else None
        picked = next((c["text"] for c in served["choices"] if c["index"] == choice), None)
        lost.setdefault(q["skill_id"], {"id": q["skill_id"], "name": skill["name"], "missed": 0})["missed"] += 1
        missed.append({"skill_id": q["skill_id"], "skill_name": skill["name"], "question": served["question"], "picked": picked,
                       "mistake": {"name": mistake["name"], "tip": mistake["tip"]} if mistake else None})
    right = sum(1 for q in row["questions"] if _right(bank, q, row["answers"]))
    return {"id": row["id"], "grade": row["grade"], "right": right, "total": len(row["questions"]), "timed_out": row["timed_out"],
            "lesson": row["scope"], "lost_skills": list(lost.values()), "missed": missed}
