"""How hard each question of the bank is: 1 easy (קל), 2 medium (בינוני), 3 hard (קשה), decided once by hand-checked criteria into
content/difficulty.json:
  1: one step or direct recall (a definition, a property, substituting, one simple calculation, reading a figure);
  2: a standard procedure of 2-3 steps, one theorem with one inference, a short word problem, or a common trap in a short task;
  3: 4 or more steps, two ideas together, setting up a non-trivial word problem, a chain of theorems, parameters.
A question that is not listed (a lesson loaded from a worksheet) counts as medium.

Who uses it: a skill's practice round and a lesson round go from easy to hard (learning.next_in_round, rounds.draw); the practice
tests take medium and hard questions only, HARD_SHARE of them hard, and the simulation 1.5 times as many hard ones (exam.draw)."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).parent / "content" / "difficulty.json"
EASY, MEDIUM, HARD = 1, 2, 3
NAMES = {EASY: "קל", MEDIUM: "בינוני", HARD: "קשה"}


@lru_cache(maxsize=1)
def levels() -> dict[str, int]:
    try:
        return {k: int(v) for k, v in json.loads(PATH.read_text(encoding="utf-8"))["levels"].items() if int(v) in NAMES}
    except (OSError, ValueError, KeyError):
        return {}


def level(key: str) -> int:
    return levels().get(key, MEDIUM)
