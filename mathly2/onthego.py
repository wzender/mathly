"""Practice on the go (תרגול מהיר, once "תרגול בנסיעה"): a short round of questions that need no board, for a phone on a bus.

Which questions qualify is decided once, by hand-checked criteria, into content/onthego.json: a question qualifies when a student who knows
the topic can pick the answer in their head within about 30 seconds without writing anything (a definition, a property, which statement
is true, reading a figure or a graph, one simple arithmetic step). Questions that need a line of work (solving, expanding, multi-step
computing, word problems) are left out. A lesson loaded from a worksheet has none until it is classified.

A round is an m2_attempts row of kind `onthego_round` (scope: the subject) on the lesson round's sheet without the board. It draws ROUND_SIZE
questions from the student's lessons, at most PER_SKILL per skill, skills not yet mastered and the nearest test's lessons first, questions
answered least often first. Each answer is a practice answer, as in a lesson round."""
from __future__ import annotations

import json
import random
from pathlib import Path

ONTHEGO_PATH = Path(__file__).parent / "content" / "onthego.json"
KIND = "onthego_round"
ROUND_SIZE = 10
PER_SKILL = 2


def load_keys(path: Path = ONTHEGO_PATH) -> frozenset[str]:
    try:
        return frozenset(json.loads(path.read_text(encoding="utf-8"))["keys"])
    except (OSError, ValueError, KeyError):
        return frozenset()


def available(bank, keys: frozenset[str], lesson_ids: list[str]) -> dict[str, list[str]]:
    """The on-the-go questions of these lessons, by skill."""
    lessons = set(lesson_ids)
    out: dict[str, list[str]] = {}
    for skill in bank.skills:
        if skill["unit"] in lessons:
            mine = [k for k in bank.question_keys(skill["id"]) if k in keys]
            if mine:
                out[skill["id"]] = mine
    return out


def draw(bank, keys: frozenset[str], lesson_ids: list[str], states: dict[str, str], test_lessons: set[str], used: dict[str, int],
         rng: random.Random | None = None) -> list[dict]:
    """ROUND_SIZE questions, at most PER_SKILL per skill: skills not mastered and the nearest test's lessons first, then the least used
    questions, mixed so that no skill comes twice in a row when it can be helped."""
    rng = rng or random.Random()
    pool = available(bank, keys, lesson_ids)
    unit = {s["id"]: s["unit"] for s in bank.skills}
    order = sorted(pool, key=lambda s: (states.get(s) == "mastered", unit[s] not in test_lessons, rng.random()))
    picked: list[dict] = []
    for take in range(PER_SKILL):                                     # one question a skill, then a second one
        for skill in order:
            if len(picked) >= ROUND_SIZE:
                break
            left = sorted((k for k in pool[skill] if all(p["key"] != k for p in picked)), key=lambda k: (used.get(k, 0), rng.random()))
            if left:
                picked.append({"skill_id": skill, "key": left[0]})
    rng.shuffle(picked)
    for i in range(1, len(picked)):                                    # no skill twice in a row, when another can swap in
        if picked[i]["skill_id"] == picked[i - 1]["skill_id"]:
            j = next((j for j in range(i + 1, len(picked)) if picked[j]["skill_id"] != picked[i - 1]["skill_id"]), None)
            if j is not None:
                picked[i], picked[j] = picked[j], picked[i]
    return picked
