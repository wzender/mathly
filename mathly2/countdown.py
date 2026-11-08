"""The countdown plan for a real test, and today's one task (PRD TST-2, TST-3). Pure functions: the server gathers the facts.

The plan, for a test set 9 or more days ahead (days left): until 9 finish the path; ~9 exercise test 1; ~7 exercise test 2; ~5 the
simulation (open from then until the test day); 4 to 1 review the skills that failed in the simulation, the last day a light mixed
review. For a test set `n < 9` days ahead the same order is kept and every day is scaled by n/9, rounded half up. The days are
recommendations: everything but the simulation's window may be started any time."""
from __future__ import annotations

from datetime import date

FULL = 9                                        # days of the full plan
BASE = {"ex1": 9, "ex2": 7, "sim": 5, "review_from": 4}


def _round(x: float) -> int:
    return int(x + 0.5)


def plan(test_day: date, set_day: date) -> dict:
    """The recommended days (days left) of each step. `set_day` is the day the teacher set the test, so the plan does not shift as days pass."""
    n = max(0, (test_day - set_day).days)
    scale = 1.0 if n >= FULL else n / FULL
    days = {step: _round(day * scale) if scale < 1 else day for step, day in BASE.items()}
    days["review_from"] = max(days["review_from"], 1)
    return {"n": n, **days}


def step_for(days_left: int, p: dict) -> str:
    """The step the plan recommends on a day: path, ex1, ex2, sim or review. It is the step whose recommended day is the nearest one
    still ahead (days left at or above today's), the earlier step first when days coincide; before all of them, the path."""
    steps = [("ex1", p["ex1"]), ("ex2", p["ex2"]), ("sim", p["sim"]), ("review", p["review_from"])]
    ahead = [(day, i, name) for i, (name, day) in enumerate(steps) if day >= days_left]
    return min(ahead)[2] if ahead else "path"


def sim_open(days_left: int, p: dict) -> bool:
    """The simulation is open from `sim` days before the test until the test day."""
    return 0 <= days_left <= p["sim"]


def outline(p: dict, facts: dict) -> list[dict]:
    """The plan as steps with their recommended day (days left) and whether they are done, for the test's card."""
    return [{"id": "path", "day": None, "until": p["ex1"], "done": facts["path_done"]},
            {"id": "ex1", "day": p["ex1"], "done": facts["ex1_done"]},
            {"id": "ex2", "day": p["ex2"], "done": facts["ex2_done"]},
            {"id": "sim", "day": p["sim"], "done": facts["sim_taken"]},
            {"id": "review", "day": p["review_from"], "done": facts["sim_taken"] and not facts["review_left"]}]


def task(days_left: int, p: dict, facts: dict) -> dict:
    """The one task for today. `facts`: path_done, next_path_skill, ex1_done, ex2_done, sim_taken, review_left (failed skills not
    practised since), stale (covered skills, the one answered longest ago first). Returns {"kind": ...} with kind one of path, ex1, ex2,
    sim, review, mixed_review, continue. The recommended step comes first; when it is done, the next later step that can be started."""
    done = {"path": facts["path_done"], "ex1": facts["ex1_done"], "ex2": facts["ex2_done"], "sim": facts["sim_taken"], "review": False}
    order = ["path", "ex1", "ex2", "sim", "review"]

    def can(step: str) -> bool:
        if step == "sim":
            return sim_open(days_left, p)                           # the simulation cannot start before its window
        return step != "review" or facts["sim_taken"]               # a review needs the simulation's result

    def make(step: str) -> dict:
        if step == "path":
            return {"kind": "path", "skill": facts["next_path_skill"]}
        if step == "review":
            if days_left == 1 or not facts["review_left"]:
                return {"kind": "mixed_review", "skill": facts["stale"][0] if facts["stale"] else None}
            return {"kind": "review", "skill": facts["review_left"][0]}
        return {"kind": step}

    if days_left < 0:
        return {"kind": "continue"}
    rec = step_for(days_left, p)
    if rec == "review" and not facts["sim_taken"]:                  # a review needs the simulation first
        rec = "sim"
    if days_left == 0 and facts["sim_taken"]:                       # the test day: nothing left to plan
        return {"kind": "continue"}
    for step in order[order.index(rec):]:                           # the recommended step, then later ones, early
        if not done[step] and can(step):
            return make(step)
    return {"kind": "continue"}


def closest(tests: list[dict], today: date) -> dict | None:
    """The nearest test that has not passed (its day is today or later)."""
    coming = [t for t in tests if t["date"] >= today]
    return min(coming, key=lambda t: (t["date"], t["id"])) if coming else None
