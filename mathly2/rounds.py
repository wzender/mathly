"""Lesson rounds (סבב שיעור): a short round of a lesson's skills with instant feedback, played from the home's map.

A round is an m2_attempts row of kind `lesson_round` (scope: the lesson id). It draws from the lesson's skills that are not mastered, at most
PER_SKILL questions from each and ROUND_SIZE in all, so it gets shorter as the lesson fills up; a lesson whose skills are all mastered draws
ROUND_SIZE from all of them. The questions are answered in order, each once, and every answer is also a practice answer of its skill (it counts
for mastery and the daily goal; a wrong one goes to the review list). After the last answer the round is graded and closed.

A lesson's stars: 3 when every skill is mastered, else 2 when a finished round had at least TWO_STARS percent right, else 1 when a round was
finished, else 0. Nothing here ever says which choice was right."""
from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import attempts, clock, quiz, reads
from .access import learner
from .learning import MASTERED, record_practice_answer, skill_state

log = logging.getLogger("mathly2.rounds")
router = APIRouter(prefix="/api")

KIND = "lesson_round"
ROUND_SIZE = 10
PER_SKILL = 3          # three right in a row is what mastery needs, so a skill never takes more of a round
TWO_STARS = 80         # percent right in a finished round for the second star


class RoundAnswer(BaseModel):
    key: str
    choice: int


def stars(skill_states: list[str], best: int | None) -> int:
    """The lesson's stars from its skills' states and the best grade of its finished rounds (None: no round finished)."""
    if skill_states and all(s == MASTERED for s in skill_states):
        return 3
    if best is None:
        return 0
    return 2 if best >= TWO_STARS else 1


def facts(rows: list[dict]) -> dict[str, dict]:
    """Per lesson with rounds: {best, finished, open} from the student's round attempts (oldest first)."""
    found: dict[str, dict] = {}
    for row in rows:
        item = found.setdefault(row["scope"], {"best": None, "finished": 0, "open": None})
        if attempts.is_open(row):
            item["open"] = row["id"]
        else:
            item["finished"] += 1
            item["best"] = row["grade"] if item["best"] is None else max(item["best"], row["grade"])
    return found


def draw(bank, lesson_id: str, states: dict[str, str], used: dict[str, int] | None = None, rng=None) -> list[dict]:
    """The questions of a new round: from the skills not mastered (all of them when every one is), the least-used first."""
    skills = [s["id"] for s in bank.skills if s["unit"] == lesson_id and bank.question_keys(s["id"])]
    left = {s for s in skills if states.get(s) != MASTERED}
    if not left:
        return quiz.draw(bank, lesson_id, used, rng, size=ROUND_SIZE)
    return quiz.draw(bank, lesson_id, used, rng, size=min(ROUND_SIZE, PER_SKILL * len(left)), skill_ids=left)


def _lesson(request: Request, user: dict, lesson_id: str) -> dict:
    from .skills import visible_lesson_ids
    lesson = next((l for l in request.app.state.bank.lessons if l["id"] == lesson_id), None)
    shown = visible_lesson_ids(request, user)
    if lesson is None or (shown is not None and lesson_id not in shown):
        raise HTTPException(404, "השיעור לא נמצא")
    return lesson


def _graded(bank, row: dict) -> list[tuple[dict, bool, dict | None]]:
    """The answered questions in order: (question ref, right, mistake)."""
    out = []
    for q in row["questions"]:
        choice = row["answers"].get(q["key"])
        if not isinstance(choice, int):
            break
        graded = bank.grade(q["skill_id"], q["key"], choice) or {"correct": False, "mistake": None}
        out.append((q, graded["correct"], graded["mistake"]))
    return out


def _when(value) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _lesson_stars(request: Request, uid: str, lesson_id: str, rows: list[dict]) -> int:
    bank, store = request.app.state.bank, request.app.state.store
    states = {p["skill_id"]: skill_state(p) for p in store.progress_of(uid)}
    lesson_skills = [s["id"] for s in bank.skills if s["unit"] == lesson_id]
    return stars([states.get(s, "not_started") for s in lesson_skills], facts(rows).get(lesson_id, {}).get("best"))


def view(request: Request, row: dict) -> dict:
    """An open round: its size, a result per answered question and the next question (without the right answer). A finished round: its result."""
    bank, store = request.app.state.bank, request.app.state.store
    lesson = next((l for l in bank.lessons if l["id"] == row["scope"]), {"id": row["scope"], "name": row["scope"]})
    done = _graded(bank, row)
    base = {"id": row["id"], "lesson": {"id": lesson["id"], "name": lesson["name"]}, "subject_id": lesson.get("subject_id", "math"), "total": len(row["questions"]),
            "results": [right for _, right, _ in done]}
    if attempts.is_open(row):
        nxt = row["questions"][len(done)] if len(done) < len(row["questions"]) else None
        served = bank.practice_question(nxt["skill_id"], nxt["key"]) if nxt else None
        return {**base, "state": "open", "question": {**served, "skill_name": bank.skill(nxt["skill_id"])["name"]} if served else None}
    uid = row["user_id"]
    progress = {p["skill_id"]: p for p in store.progress_of(uid)}
    started = _when(row["started_at"])
    by_skill: dict[str, list[bool]] = {}
    for q, right, _ in done:
        by_skill.setdefault(q["skill_id"], []).append(right)
    mastered, almost = [], []
    for skill_id, results in by_skill.items():
        p, skill = progress.get(skill_id), bank.skill(skill_id)
        if skill is None:
            continue
        item = {"id": skill_id, "name": skill["name"]}
        if p and p.get("mastered_at"):
            if started and _when(p["mastered_at"]) >= started:
                mastered.append(item)
        elif len(results) >= 2 and all(results):
            almost.append(item)                                   # right in a row today: one more good answer on another day masters it
    missed = []
    for q, right, mistake in done:
        if right:
            continue
        served = bank.practice_question(q["skill_id"], q["key"])
        missed.append({"question": served["question"] if served else "", "skill_name": (bank.skill(q["skill_id"]) or {}).get("name", ""),
                       "mistake": {"name": mistake["name"], "tip": mistake["tip"]} if mistake else None})
    all_rows = store.attempts_of(uid, KIND, row["scope"])
    return {**base, "state": "done", "question": None,
            "result": {"right": sum(base["results"]), "total": base["total"], "grade": row["grade"], "stars": _lesson_stars(request, uid, row["scope"], all_rows),
                       "mastered": mastered, "almost": almost, "missed": missed}}


def _mine(request: Request, user: dict, round_id: str) -> dict:
    row = request.app.state.store.get_attempt(round_id)
    if row is None or row["user_id"] != user["id"] or row["kind"] != KIND:
        raise HTTPException(404, "הסבב לא נמצא")
    return row


@router.post("/lessons/{lesson_id}/round/start")
def start(lesson_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """Resume the lesson's open round, else draw a new one."""
    _lesson(request, user, lesson_id)
    store, bank, here, uid = request.app.state.store, request.app.state.bank, reads.of(request), user["id"]
    here.prefetch(("attempts_of", uid, KIND, lesson_id), ("progress_of", uid))
    mine = here.attempts_of(uid, KIND, lesson_id)
    for row in mine:
        if attempts.is_open(row):
            return view(request, row)
    states = {p["skill_id"]: skill_state(p) for p in here.progress_of(uid)}
    used = Counter(q["key"] for row in mine for q in row["questions"])
    drawn = draw(bank, lesson_id, states, used, getattr(request.app.state, "quiz_rng", None))
    if not drawn:
        raise HTTPException(409, "אין עדיין שאלות בשיעור הזה")
    now = clock.now()
    row = store.create_attempt(uid, KIND, lesson_id, now, now + timedelta(days=365), drawn)    # untimed: the due date is never used
    return view(request, row)


@router.get("/rounds/{round_id}")
def read(round_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    return view(request, _mine(request, user, round_id))


@router.post("/rounds/{round_id}/answer")
def answer(round_id: str, body: RoundAnswer, request: Request, user: dict = Depends(learner)) -> dict:
    """Grade the next question of the round at once; store it as a practice answer; close the round after its last question."""
    store, bank, uid = request.app.state.store, request.app.state.bank, user["id"]
    row = _mine(request, user, round_id)
    if not attempts.is_open(row):
        raise HTTPException(409, "הסבב כבר הסתיים")
    answered = len(_graded(bank, row))
    expected = row["questions"][answered] if answered < len(row["questions"]) else None
    if expected is None or expected["key"] != body.key:
        raise HTTPException(409, "השאלה הזו כבר לא על המסך")
    graded = bank.grade(expected["skill_id"], body.key, body.choice)
    if graded is None:
        raise HTTPException(422, "תשובה לא חוקית")
    saved = store.save_open_answers(row["id"], {**row["answers"], body.key: body.choice})
    if saved is None:
        raise HTTPException(409, "הסבב כבר הסתיים")
    skill_id, correct, mistake = expected["skill_id"], graded["correct"], graded["mistake"]
    before = store.get_progress(uid, skill_id)
    progress = record_practice_answer(store, uid, skill_id, body.key, correct, True, mistake["id"] if mistake else None,
                                      clock.school_day(), clock.now().isoformat())
    mastered_now = not (before or {}).get("mastered_at") and bool(progress.get("mastered_at"))
    if not correct:
        try:
            store.add_review(uid, [(skill_id, body.key, "practice")], clock.now())
        except Exception as exc:                                              # bookkeeping never fails an answer
            log.warning("could not add a wrong round answer to the review list: %s", type(exc).__name__)
    if len(saved["answers"]) >= len(saved["questions"]):
        right = sum(1 for _, r, _ in _graded(bank, saved) if r)
        saved = store.save_attempt(saved["id"], submitted_at=clock.now(), timed_out=False,
                                   grade=attempts.percent(right, len(saved["questions"])), answers=saved["answers"])
    if mistake and mistake.get("back"):
        back = bank.skill(mistake["back"])
        mistake = {**mistake, "back_name": back["name"] if back else None}
    return {"correct": correct, "mistake": mistake, "mastered_now": {"id": skill_id, "name": bank.skill(skill_id)["name"]} if mastered_now else None,
            "round": view(request, saved)}
