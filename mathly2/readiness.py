"""The readiness number for a real test: one 0-100 number that only tests move (practice tests and simulations), never the path.

Every handed-in test pulls the number toward its grade, and only up: a grade above the number closes part of the gap, a grade at or below
it changes nothing. A simulation closes more of the gap than a practice test; a practice test on skills the student picked closes less
(it can skip the hard ones). So the number is never above the best grades, and the way up is more good tests, best of all a simulation.

    number' = number + GAIN[kind] * (grade - number)   when grade > number
"""
from __future__ import annotations

GAIN = {"simulation": 0.6, "practice": 0.3, "manual": 0.15}
LEVELS = [(0, "מתחילים"), (40, "בדרך"), (70, "כמעט שם"), (85, "מוכנים")]


def label(number: int) -> str:
    return [name for at, name in LEVELS if number >= at][-1]


def next_level(number: int) -> dict | None:
    """The next level above the number: {"at", "name", "left"} (points left), or None at the top."""
    above = [(at, name) for at, name in LEVELS if at > number]
    return {"at": above[0][0], "name": above[0][1], "left": above[0][0] - number} if above else None


def step(value: float, kind: str, grade: float) -> float:
    return value + GAIN[kind] * (grade - value) if grade > value else value


def compute(results: list[tuple[str, int]]) -> dict:
    """`results`: the handed-in tests of one real test, oldest first, as (kind, grade) with kind simulation, practice or manual."""
    value = 0.0
    for kind, grade in results:
        value = step(value, kind, grade)
    number = max(0, min(100, int(value + 0.5)))
    best = lambda kinds: max((g for k, g in results if k in kinds), default=None)
    return {"number": number, "label": label(number), "next": next_level(number),
            "practices": sum(1 for k, _ in results if k != "simulation"), "simulations": sum(1 for k, _ in results if k == "simulation"),
            "practice_best": best(("practice", "manual")), "simulation_best": best(("simulation",)),
            "can_add": {k: max(0, int(GAIN[k] * (100 - value) + 0.5)) for k in GAIN}}          # what a perfect test of each kind would add now


def change(before: list[tuple[str, int]], result: tuple[str, int]) -> dict:
    """What one handed-in test did to the number: before, after, the gain, and whether it reached a new level."""
    old, new = compute(before), compute([*before, result])
    return {"before": old["number"], "after": new["number"], "gain": new["number"] - old["number"], "label": new["label"],
            "level_up": new["label"] != old["label"], "next": new["next"]}
