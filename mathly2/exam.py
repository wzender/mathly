"""Drawing an exercise test or a simulation for a real test (PRD EXT-4, EXT-5, SIM-2): mixed questions from all covered lessons,
weighted toward the student's weak skills, never from a skill the student has not started."""
from __future__ import annotations

import random

EXERCISE_SHARE = {1: 0.6, 2: 0.3}      # the share of questions that come from weak skills in exercise test 1 and 2; the simulation has none


def _round(x: float) -> int:
    return int(x + 0.5)


def draw(bank, lessons: list[str], states: dict[str, str], n: int, *, share: float = 0.0, weak_before: set[str] | None = None,
         used: dict[str, int] | None = None, rng: random.Random | None = None, include_unstarted: bool = False) -> dict:
    """{"questions": [{skill_id, key}], "weak": [skill ids], "practice_first": [skill ids]}.

    Covered skills are those of `lessons` that have questions. A skill in the not-started state is never drawn: it is listed in
    `practice_first`. A weak skill is a started covered skill in the learning state, or one in `weak_before` (answered wrong in an
    earlier exercise test of this real test). With `include_unstarted`, not-started skills are drawn too (and still listed in `practice_first`). Weak skills give one question each, up to `round(n * share)`; the rest comes from the
    other skills one per skill round after round (least-used questions first, ties random), then from the weak ones again."""
    used, rng, weak_before = used or {}, rng or random.Random(), weak_before or set()
    covered = [s["id"] for s in bank.skills if s["unit"] in lessons and bank.question_keys(s["id"])]
    started = [i for i in covered if states.get(i, "not_started") != "not_started"]
    practice_first = [i for i in covered if i not in started]
    if include_unstarted:
        started = covered
    weak = [i for i in started if states.get(i) == "learning" or i in weak_before]
    other = [i for i in started if i not in weak]
    pools = {i: sorted(bank.question_keys(i), key=lambda key: (used.get(key, 0), rng.random())) for i in started}
    taken: list[dict] = []
    seen: set[str] = set()

    def take(skill_id: str) -> bool:
        for key in pools[skill_id]:
            if key not in seen:
                seen.add(key)
                taken.append({"skill_id": skill_id, "key": key})
                return True
        return False

    wanted = _round(n * share)
    shuffled_weak = rng.sample(weak, len(weak))
    for skill_id in shuffled_weak[:wanted]:
        take(skill_id)
    order = rng.sample(other, len(other)) if share else rng.sample(started, len(started))        # no weak share: an even spread over all
    for group in ([order, shuffled_weak] if share else [order]):    # the weak skills are used again only when the others run out
        progress = True
        while len(taken) < n and progress:
            progress = False
            for skill_id in group:
                if len(taken) >= n:
                    break
                if take(skill_id):
                    progress = True
    rng.shuffle(taken)
    return {"questions": taken[:n], "weak": weak, "practice_first": practice_first}
