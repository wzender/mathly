"""Unit-quiz grades, worked out on the server from the stored checks.

A sitting (Supabase `math_quiz_sittings`, written when the student hands the quiz in) lists its attempts in question
order. The database says, for each, whether it has a saved photo and what its latest check is; the quiz's points per
question are in app/math_algebra9.json. The grade is computed here every time it is read, so it follows a check that
finishes later (for example one the teacher sends from the AI queue), and nothing the student's device uploads can
change it. Both the student's result screen and the class report use `sitting_view`.
"""
from __future__ import annotations

from .math_skills import algebra9


def question_result(points: int, attempt: dict | None) -> dict:
    """One question of a sitting: its points, what it earned (None while its check is open) and why."""
    if not attempt or not attempt.get("has_photo"):
        return {"points": points, "earned": 0, "state": "missing"}
    score = attempt.get("score")
    if attempt.get("grade_state") == "completed" and type(score) is int and 0 <= score <= 100:
        return {"points": points, "earned": int(points * score / 100 + 0.5), "state": "checked",
                "verdict": attempt.get("verdict")}
    if attempt.get("grade_state") == "completed":   # a check without a score: unreadable, or needs a teacher's look
        return {"points": points, "earned": None, "state": attempt.get("verdict") or "waiting"}
    return {"points": points, "earned": None, "state": "waiting"}


def sitting_view(sitting: dict, units: list[dict] | None = None) -> dict | None:
    """A stored sitting as the page reads it: when, the grade (None while an answer is open), the open count and
    each question's points. None for a unit that has no quiz."""
    unit = next((u for u in units or algebra9()["units"] if u["id"] == sitting.get("unit_id")), None)
    if not unit or "quiz" not in unit:
        return None
    attempts = sitting.get("attempts") or []
    questions = [question_result(q["points"], attempts[i] if i < len(attempts) else None)
                 for i, q in enumerate(unit["quiz"]["questions"])]
    open_count = sum(1 for q in questions if q["earned"] is None)
    return {"id": sitting["id"], "unit_id": unit["id"], "submitted_at": sitting.get("submitted_at"),
            "time_up": bool(sitting.get("time_up")), "attempts": [a.get("attempt_id") for a in attempts],
            "questions": questions, "open": open_count,
            "grade": None if open_count else sum(q["earned"] for q in questions)}
