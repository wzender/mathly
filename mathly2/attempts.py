"""Timed, graded attempts (the engine under lesson quizzes; exercise tests and the simulation will use it too).

An attempt is open until it is graded. The server settles an overdue attempt on the first read after its deadline, so there is no
background job and the answer is right even if nothing ran at the deadline. Nothing here ever says which choice was right."""
from __future__ import annotations

from datetime import datetime

QUIZ_SIZE = 10
QUIZ_MINUTES = 15


def percent(right: int, total: int) -> int:
    """The grade: the share of right answers as a whole number 0-100, rounded half up (7/10 -> 70, 8/12 -> 67)."""
    return 0 if total <= 0 else (200 * right + total) // (2 * total)


def _right(bank, question: dict, answers: dict) -> bool:
    choice = answers.get(question["key"])
    graded = bank.grade(question["skill_id"], question["key"], choice) if isinstance(choice, int) else None
    return bool(graded and graded["correct"])


def grade(bank, questions: list[dict], answers: dict) -> tuple[int, int]:
    """(grade, number right). A question without an answer, or with an answer the bank does not know, is wrong."""
    right = sum(1 for q in questions if _right(bank, q, answers))
    return percent(right, len(questions)), right


def is_open(row: dict) -> bool:
    return row["submitted_at"] is None


def is_overdue(row: dict, now: datetime) -> bool:
    return is_open(row) and now >= row["due_at"]


def settle(store, bank, row: dict, now: datetime) -> dict:
    """Grade an overdue open attempt from the answers saved so far. Anything else is returned as it is."""
    if not is_overdue(row, now):
        return row
    value, _ = grade(bank, row["questions"], row["answers"])
    return store.save_attempt(row["id"], submitted_at=row["due_at"], timed_out=True, grade=value)


def submit(store, bank, row: dict, now: datetime) -> dict:
    """The student hands in. Idempotent: a submitted attempt is returned unchanged; one past its deadline is settled as timed out."""
    if not is_open(row):
        return row
    if is_overdue(row, now):
        return settle(store, bank, row, now)
    value, _ = grade(bank, row["questions"], row["answers"])
    return store.save_attempt(row["id"], submitted_at=now, timed_out=False, grade=value)


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
