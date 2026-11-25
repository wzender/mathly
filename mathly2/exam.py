"""Drawing an exercise test or a simulation for a real test (PRD EXT-4, EXT-5, SIM-2): mixed questions from all covered lessons,
weighted toward the student's weak skills, never from a skill the student has not started."""
from __future__ import annotations

import random

from .difficulty import EASY, HARD, MEDIUM, level

EXERCISE_SHARE = {1: 0.6, 2: 0.3}      # the share of questions that come from weak skills in exercise test 1 and 2; the simulation has none
FOCUS = 3                               # the exercise test on the weak topics: only the skills that lost points or are still being learned
FOCUS_SIZE = 15
BALANCED, MANUAL = 1, 4                 # practice tests by mode (the number in the attempt's scope "<test>:<n>"); 2 is an older balanced one
MODE_OF = {1: "balanced", 2: "balanced", FOCUS: "focus", MANUAL: "manual"}
NUMBER_OF = {"balanced": BALANCED, "focus": FOCUS, "manual": MANUAL}
PRACTICE_HARD = 0.4                     # the share of hard questions in a practice test (the rest medium; no easy ones)
SIMULATION_HARD = PRACTICE_HARD * 1.5   # the simulation: 1.5 times as many hard questions (0.6)
TITLES = {"balanced": "מבחן תרגול מאוזן", "focus": "מבחן תרגול ממוקד", "manual": "מבחן תרגול בבחירה"}


def mode_of_scope(scope: str) -> str:
    _, _, number = scope.partition(":")
    return MODE_OF.get(int(number), "balanced") if number.isdigit() else "balanced"


def _round(x: float) -> int:
    return int(x + 0.5)


class _Picker:
    """Takes questions skill by skill: medium and hard only (easy ones only when nothing else is left), `hard_share` of them hard, spread
    over the test. Questions the student had less often come first whatever their level (a retake gets new questions while there are),
    then the wanted level; each pool is already least-used first, ties random."""
    def __init__(self, pools: dict[str, list[str]], n: int, hard_share: float, used: dict[str, int]):
        self.pools, self.n, self.hard_target, self.used = pools, n, _round(n * hard_share), used
        self.taken: list[dict] = []
        self.seen: set[str] = set()
        self.hard = 0
        self.allow_easy = False

    def take(self, skill_id: str) -> bool:
        want_hard = self.hard * self.n < self.hard_target * (len(self.taken) + 1)
        rank = {lv: i for i, lv in enumerate([HARD, MEDIUM] if want_hard else [MEDIUM, HARD])}
        if self.allow_easy:
            rank[EASY] = 2
        free = [(self.used.get(k, 0), rank[level(k)], i, k) for i, k in enumerate(self.pools[skill_id]) if k not in self.seen and level(k) in rank]
        if not free:
            return False
        key = min(free)[3]
        self.seen.add(key)
        self.taken.append({"skill_id": skill_id, "key": key})
        self.hard += level(key) == HARD
        return True

    def fill(self, groups: list[list[str]]) -> None:
        """One question per skill, round after round, group after group, until n; easy questions only if the rest cannot fill it."""
        for allow_easy in (False, True):
            self.allow_easy = allow_easy
            for group in groups:
                progress = True
                while len(self.taken) < self.n and progress:
                    progress = False
                    for skill_id in group:
                        if len(self.taken) >= self.n:
                            break
                        if self.take(skill_id):
                            progress = True


def draw(bank, lessons: list[str], states: dict[str, str], n: int, *, share: float = 0.0, weak_before: set[str] | None = None,
         used: dict[str, int] | None = None, rng: random.Random | None = None, include_unstarted: bool = False,
         hard_share: float = PRACTICE_HARD) -> dict:
    """{"questions": [{skill_id, key}], "weak": [skill ids], "practice_first": [skill ids]}.

    Covered skills are those of `lessons` that have questions. A skill in the not-started state is never drawn: it is listed in
    `practice_first`. A weak skill is a started covered skill in the learning state, or one in `weak_before` (answered wrong in an
    earlier exercise test of this real test). With `include_unstarted`, not-started skills are drawn too (and still listed in `practice_first`).
    Weak skills give one question each, up to `round(n * share)`; the rest comes from the other skills one per skill round after round
    (least-used questions first, ties random), then from the weak ones again. Only medium and hard questions (difficulty.py), `hard_share`
    of them hard (PRACTICE_HARD for a practice test, SIMULATION_HARD for the simulation); easy ones only when nothing else is left."""
    used, rng, weak_before = used or {}, rng or random.Random(), weak_before or set()
    covered = [s["id"] for s in bank.skills if s["unit"] in lessons and bank.question_keys(s["id"])]
    started = [i for i in covered if states.get(i, "not_started") != "not_started"]
    practice_first = [i for i in covered if i not in started]
    if include_unstarted:
        started = covered
    weak = [i for i in started if states.get(i) == "learning" or i in weak_before]
    other = [i for i in started if i not in weak]
    pools = {i: sorted(bank.question_keys(i), key=lambda key: (used.get(key, 0), rng.random())) for i in started}
    pick = _Picker(pools, n, hard_share, used)
    shuffled_weak = rng.sample(weak, len(weak))
    for skill_id in shuffled_weak[:_round(n * share)]:
        pick.take(skill_id)
    order = rng.sample(other, len(other)) if share else rng.sample(started, len(started))        # no weak share: an even spread over all
    pick.fill([order, shuffled_weak] if share else [order])          # the weak skills are used again only when the others run out
    taken = pick.taken
    rng.shuffle(taken)
    return {"questions": taken[:n], "weak": weak, "practice_first": practice_first}


def draw_focus(bank, weak: list[str], n: int = FOCUS_SIZE, used: dict[str, int] | None = None, rng: random.Random | None = None,
               hard_share: float = PRACTICE_HARD) -> list[dict]:
    """`n` questions from these skills only (the weak ones, or the ones the student picked), one per skill round after round (least-used
    first), medium and hard only as in draw."""
    used, rng = used or {}, rng or random.Random()
    pools = {i: sorted(bank.question_keys(i), key=lambda key: (used.get(key, 0), rng.random())) for i in weak if bank.question_keys(i)}
    pick = _Picker(pools, n, hard_share, used)
    pick.fill([rng.sample(list(pools), len(pools))])
    taken = pick.taken
    rng.shuffle(taken)
    return taken
