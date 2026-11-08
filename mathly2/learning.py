"""The rules of skill learning. Pure functions plus `record_practice_answer`; they work on any store.
Every day is decided by the server (`clock.school_day`), never by the device."""
from __future__ import annotations

import random
from datetime import date, timedelta

MASTERY_RUN = 3        # correct answers in a row...
MASTERY_DAYS = 2       # ...spread over at least this many different calendar days
FADE_DAYS = 14         # a mastered skill not answered for this many days shows a faded star (a visual cue only)
DAILY_GOAL = 5         # correct answers a day that count toward the streak

NOT_STARTED, LEARNING, MASTERED = "not_started", "learning", "mastered"


def is_mastered(last_counted: list[dict]) -> bool:
    """`last_counted`: the student's counted practice answers on a skill, oldest first.
    Mastered when the last 3 are all correct and fall on 2 or more different days.
    Answers given with help are not in the list: they neither extend nor break the run."""
    run = last_counted[-MASTERY_RUN:]
    return (len(run) == MASTERY_RUN and all(a["correct"] for a in run)
            and len({a["day"] for a in run}) >= MASTERY_DAYS)


def skill_state(progress: dict | None) -> str:
    if progress and progress.get("mastered_at"):
        return MASTERED                      # never decays: nothing later can clear mastered_at
    if progress and progress.get("started_at"):
        return LEARNING
    return NOT_STARTED


def mark_started(store, user_id: str, skill_id: str, now: str) -> dict:
    """A first answer moves a skill out of 'not started'."""
    progress = store.get_progress(user_id, skill_id)
    if progress and progress.get("started_at"):
        return progress
    return store.save_progress(user_id, skill_id, started_at=now)


def record_practice_answer(store, user_id: str, skill_id: str, question_key: str, correct: bool, counted: bool,
                           mistake_id: str | None, day: date, now: str) -> dict:
    """Store one practice answer, then set `mastered_at` the first time the mastery rule is met.
    Returns the progress row."""
    mark_started(store, user_id, skill_id, now)
    store.add_answer(user_id, skill_id, question_key, correct, counted, mistake_id, day)
    progress = store.get_progress(user_id, skill_id)
    if not progress.get("mastered_at") and is_mastered(store.last_counted_answers(user_id, skill_id, MASTERY_RUN)):
        progress = store.save_progress(user_id, skill_id, mastered_at=now)
    return progress


def answer_counts(rows: list[dict]) -> dict[str, int]:
    """How often each question was answered, from the student's answers on a skill."""
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["question_key"]] = counts.get(r["question_key"], 0) + 1
    return counts


def solved_keys(rows: list[dict]) -> set[str]:
    """The questions answered correctly at least once (with or without help)."""
    return {r["question_key"] for r in rows if r["correct"]}


def last_counted(rows: list[dict]) -> list[dict]:
    """The last MASTERY_RUN answers that were not given with help, oldest first: what the mastery rule looks at."""
    return [r for r in rows if r["counted"]][-MASTERY_RUN:]


def current_round(keys: list[str], rows: list[dict], round_start: int | None) -> dict:
    """The round in progress on a skill: its practice questions (`keys`), each answered once. `rows` are all the student's answers on the
    skill, oldest first, and the round is the answers from `round_start` on (null: the student practised before rounds existed, so all
    their answers are past rounds and a new one begins). Returns the answers of the round in order, the questions not answered yet and
    whether the round is done."""
    wanted, seen, taken = set(keys), set(), []
    for row in (rows[round_start:] if round_start is not None else []):
        if row["question_key"] in wanted and row["question_key"] not in seen:
            seen.add(row["question_key"])
            taken.append(row)
    left = [k for k in keys if k not in seen]
    return {"answers": taken, "left": left, "done": bool(keys) and not left}


def next_in_round(left: list[str], just_answered: str | None = None, rng: random.Random | None = None) -> str | None:
    """The next question of the round: one not answered yet, at random; none when the round is done."""
    candidates = [k for k in left if k != just_answered]
    return (rng or random).choice(candidates) if candidates else None


def next_skill(order: list[str], states: dict[str, str], recent: list[str]) -> str | None:
    """The suggested next skill: the unmastered skill the student answered most recently (`recent`, newest first), else the
    first unmastered skill in `order` (the bank's order, among the skills the student can see). None when everything is mastered.
    Only a suggestion: nothing is locked, hidden or reordered by it."""
    visible = set(order)
    for skill_id in recent:
        if skill_id in visible and states.get(skill_id) != MASTERED:
            return skill_id
    return next((skill_id for skill_id in order if states.get(skill_id) != MASTERED), None)


def is_faded(state: str, last_answered: date | None, today: date) -> bool:
    """A faded star: mastered, and not answered for FADE_DAYS days. It never changes the state itself."""
    return state == MASTERED and last_answered is not None and (today - last_answered).days >= FADE_DAYS


def today_progress(daily: dict[date, int], today: date) -> dict:
    done = daily.get(today, 0)
    return {"done": done, "goal": DAILY_GOAL, "reached": done >= DAILY_GOAL}


def streak(daily: dict[date, int], today: date) -> int:
    """Consecutive days with at least the daily goal. Today counts once reached; until then the streak is kept
    (it is still alive) and counted up to yesterday."""
    day = today if daily.get(today, 0) >= DAILY_GOAL else today - timedelta(days=1)
    days = 0
    while daily.get(day, 0) >= DAILY_GOAL:
        days += 1
        day -= timedelta(days=1)
    return days
