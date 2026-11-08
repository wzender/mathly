"""Drawing a lesson quiz: 10 multiple-choice questions from the lesson's skills, spread evenly, new questions first on a retake."""
from __future__ import annotations

import random

from .attempts import QUIZ_SIZE


def draw(bank, lesson_id: str, used: dict[str, int] | None = None, rng: random.Random | None = None, size: int = QUIZ_SIZE) -> list[dict]:
    """[{skill_id, key}] in a shuffled order. Skills without questions are left out. Each skill gets `size // k` questions and the
    remainder goes to distinct skills picked at random, so quotas differ by at most one. Within a skill the least-used questions come
    first (`used`: how often the student had each question key in earlier quizzes of this lesson), ties in random order."""
    used, rng = used or {}, rng or random.Random()
    skills = [s for s in bank.skills if s["unit"] == lesson_id and bank.question_keys(s["id"])]
    if not skills:
        return []
    quota = {s["id"]: size // len(skills) for s in skills}
    for skill in rng.sample(skills, size % len(skills)):
        quota[skill["id"]] += 1
    pools = {s["id"]: sorted(bank.question_keys(s["id"]), key=lambda key: (used.get(key, 0), rng.random())) for s in skills}
    for skill_id in quota:                                    # a skill with too few questions gives all it has; others take the slack
        quota[skill_id] = min(quota[skill_id], len(pools[skill_id]))
    slack = size - sum(quota.values())
    while slack > 0:
        room = [i for i in quota if quota[i] < len(pools[i])]
        if not room:
            break
        quota[min(room, key=lambda i: (quota[i], rng.random()))] += 1
        slack -= 1
    chosen = [{"skill_id": i, "key": key} for i in quota for key in pools[i][:quota[i]]]
    rng.shuffle(chosen)
    return chosen


def facts(store, bank, user_id: str, now, reads=None) -> dict[str, dict]:
    """Per lesson the student has attempted: {best, attempts, open, last}. Overdue open attempts are settled first, so a quiz abandoned
    past its deadline is graded from the answers given. `best` is None until an attempt is submitted."""
    from . import attempts
    found: dict[str, dict] = {}
    for row in (reads or store).attempts_of(user_id, "quiz"):
        row = attempts.settle(store, bank, row, now)
        item = found.setdefault(row["scope"], {"best": None, "attempts": 0, "open": None, "last": None})
        if attempts.is_open(row):
            item["open"] = {"id": row["id"], "due_at": row["due_at"]}
            continue
        item["attempts"] += 1
        item["best"] = row["grade"] if item["best"] is None else max(item["best"], row["grade"])
        item["last"] = row["submitted_at"]
    return found
