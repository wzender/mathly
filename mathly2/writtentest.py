"""The written simulation (מבחן סימולציה כתוב): like a real exam, a question has no choices. The student writes the way on the question's
board and, when the answer is a plain number (5, x = 5, 70°, 1/4), types it in a box too. After the hand-in the AI judges each board
(boardreview.py) and the grade is set from its verdicts: right 1, partly right ½, wrong or unreadable 0; a question with nothing on its
board is unanswered (0). A teacher's credit for a question (0, ½, 1) replaces the AI's. Until every board with work is judged (or the
teacher checked the test) the grade is empty: "waiting for the check". Without the AI the teacher checks it.

The typed answer is never graded by itself: it goes to the AI with the board, with whether it matches the right answer."""
from __future__ import annotations

import logging
import re
from fractions import Fraction

from . import attempts

log = logging.getLogger("mathly2.written")

WRITTEN = attempts.WRITTEN_KINDS
VERDICT_POINTS = {"correct": 1.0, "partial": 0.5, "wrong": 0.0, "unclear": 0.0}
FINAL_MAX = 40                               # characters in a typed final answer

_NUMBER = r"[-−]?\d+(?:\.\d+)?(?:/\d+)?"
_SIMPLE = re.compile(rf"^(?:(?P<var>[a-zA-Z])=)?(?P<num>{_NUMBER})(?P<unit>°?)$")


def is_written(row: dict) -> bool:
    return row["kind"] in WRITTEN


def _plain(text: str) -> str:
    return re.sub(r"\s+", "", str(text or "").replace("$", "")).replace("\\frac{", "").replace("}{", "/").replace("}", "")


def _number(text: str) -> Fraction | None:
    try:
        return Fraction(text.replace("−", "-"))
    except (ValueError, ZeroDivisionError):
        return None


def right_text(bank, ref: dict) -> str | None:
    """The right choice's text (for the AI and the teacher only)."""
    served = bank.practice_question(ref["skill_id"], ref["key"])
    if not served:
        return None
    return next((c["text"] for c in served["choices"] if (bank.grade(ref["skill_id"], ref["key"], c["index"]) or {}).get("correct")), None)


def final_of(bank, ref: dict) -> dict | None:
    """When the right answer is a plain number: the box's label ("x =", or none) and unit ("°"), and the value. Else None."""
    text = right_text(bank, ref)
    match = _SIMPLE.match(_plain(text)) if text else None
    value = _number(match["num"]) if match else None
    if value is None:
        return None
    return {"label": f"{match['var']} =" if match["var"] else "", "unit": match["unit"], "value": value}


def matches(typed: str | None, final: dict | None) -> bool | None:
    """Does the typed answer equal the right one (5 = 5.0 = 10/2, "x=5" or "5°" too)? None when there is no box or nothing typed."""
    if final is None or not str(typed or "").strip():
        return None
    plain = _plain(typed).replace(",", ".").rstrip("°")
    if "=" in plain:
        plain = plain.split("=")[-1]
    value = _number(plain)
    return value is not None and value == final["value"]


def served_question(bank, ref: dict) -> dict | None:
    """A question as the student sees it in the written simulation: no choices, and the final answer's box when it has one."""
    served = bank.practice_question(ref["skill_id"], ref["key"])
    if not served:
        return None
    final = final_of(bank, ref)
    shown = {k: v for k, v in served.items() if k != "choices"}
    return {**shown, "final": {"label": final["label"], "unit": final["unit"]} if final else None}


def typed(row: dict, key: str) -> str | None:
    """The final answer the student typed (a written attempt keeps it as the answer), or None."""
    value = row["answers"].get(key)
    return value if isinstance(value, str) and value.strip() else None


def question_points(row: dict, key: str, has_work: bool) -> float | None:
    """A question's points: the teacher's credit, else the AI's verdict, else 0 with nothing on its board; None while it waits for a check."""
    given = (row.get("credit") or {}).get(key)
    if given in attempts.CREDITS:
        return float(given)
    verdict = (((row.get("review") or {}).get("questions") or {}).get(key) or {}).get("verdict")
    if verdict in VERDICT_POINTS:
        return VERDICT_POINTS[verdict]
    return 0.0 if not has_work else None


def grade_of(row: dict, work: dict, final: bool = False) -> int | None:
    """The grade from every question's points, or None while a board waits for its check. `final` (the teacher checked): a board with
    no verdict and no credit counts 0."""
    halves = 0
    for q in row["questions"]:
        got = question_points(row, q["key"], q["key"] in work)
        if got is None:
            if not final:
                return None
            got = 0.0
        halves += round(2 * got)
    return attempts.percent(halves, 2 * len(row["questions"]))


def missed_keys(row: dict, work: dict) -> list[str]:
    """The questions that did not get full points (only once the test is graded)."""
    if row["grade"] is None:
        return []
    return [q["key"] for q in row["questions"] if (question_points(row, q["key"], q["key"] in work) or 0.0) < 1.0]


def settle_grade(store, bank, row: dict, final: bool = False, at=None) -> dict:
    """Set a written attempt's grade once it can be known, and put the questions without full points in the review list (the first time).
    Returns the row as it is now."""
    if not is_written(row) or row["submitted_at"] is None:
        return row
    work = store.work_of(row["user_id"], row["id"])
    value = grade_of(row, work, final)
    if value is None or value == row["grade"]:
        return row
    first = row["grade"] is None
    saved = store.save_attempt(row["id"], grade=value)
    if first:
        wrong = [(q["skill_id"], q["key"], row["kind"]) for q in row["questions"] if q["key"] in missed_keys(saved, work)]
        if wrong:
            try:
                store.add_review(row["user_id"], wrong, at or row["submitted_at"])
            except Exception as exc:
                log.warning("could not add the written test's misses to the review list: %s", type(exc).__name__)
    return saved


def result(bank, row: dict, work: dict) -> dict:
    """What the student sees after handing in: while it waits for the check, the state "checking"; then the grade, the questions without
    full points (with the typed answer) and the skills that lost points. Never the right answer."""
    base = {"id": row["id"], "grade": row["grade"], "total": len(row["questions"]), "timed_out": row["timed_out"], "lesson": row["scope"],
            "written": True, "checking": row["grade"] is None}
    if row["grade"] is None:
        return {**base, "right": None, "lost_skills": [], "missed": []}
    lost: dict[str, dict] = {}
    missed, right = [], 0
    for q in row["questions"]:
        got = question_points(row, q["key"], q["key"] in work) or 0.0
        if got >= 1.0:
            right += 1
            continue
        skill, served = bank.skill(q["skill_id"]), bank.practice_question(q["skill_id"], q["key"])
        if skill is None or served is None:
            continue
        lost.setdefault(q["skill_id"], {"id": q["skill_id"], "name": skill["name"], "missed": 0})["missed"] += 1
        missed.append({"skill_id": q["skill_id"], "skill_name": skill["name"], "question": served["question"], "picked": typed(row, q["key"]),
                       "points": got, "no_work": q["key"] not in work, "mistake": None})
    return {**base, "right": right, "lost_skills": list(lost.values()), "missed": missed}
