"""The readiness number for a real test (PRD RDY-1 to RDY-3): one 0-100 number from mastery, exercise tests and the simulation."""
from __future__ import annotations

WEIGHTS = {"M": 50, "E": 20, "S": 30}
CAP = 80                      # the most the number can show before the simulation is taken


def label(number: int) -> str:
    if number < 40:
        return "מתחילים"
    if number < 70:
        return "בדרך"
    if number < 85:
        return "כמעט שם"
    return "מוכנים"


def compute(m: float | None, e: float | None, s: float | None) -> dict:
    """M: % of the covered skills mastered. E: average of the best grade of each exercise test taken. S: the simulation grade.
    A part that does not exist is None and is left out; the others are scaled up. Without S the number is capped at 80."""
    parts = {"M": m, "E": e, "S": s}
    have = {k: v for k, v in parts.items() if v is not None}
    if not have:
        number = 0
    else:
        number = int(sum(WEIGHTS[k] * v for k, v in have.items()) / sum(WEIGHTS[k] for k in have) + 0.5)
    capped = s is None and number > CAP
    if s is None:
        number = min(number, CAP)
    number = max(0, min(100, number))
    return {"number": number, "label": label(number), "capped": capped, "waiting_for_simulation": s is None,
            "parts": {k: (None if v is None else int(v + 0.5)) for k, v in parts.items()}}


def mastery_percent(mastered: int, covered: int) -> float | None:
    """M: None when the test covers no skill with questions."""
    return None if covered <= 0 else 100 * mastered / covered


def exercise_average(best_grades: list[int]) -> float | None:
    """E: the average of the best grade of each exercise test taken; None when none was taken."""
    return sum(best_grades) / len(best_grades) if best_grades else None
