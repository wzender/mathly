"""Practicing a skill: the question on screen, answers and help, the path and the collection.
The server decides right and wrong, the day, and mastery; the browser never receives which choice is correct
for a practice question."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import clock, comets, quiz, reads
from .access import learner
from .learning import (DAILY_GOAL, MASTERED, current_round, is_faded, is_mastered, last_counted, next_in_round, next_skill, skill_state, streak,
                       today_progress)

log = logging.getLogger("mathly2.skills")
router = APIRouter(prefix="/api")
RECENT = 30   # how many recently answered skills the "next skill" looks at


class Answer(BaseModel):
    question_key: str
    choice: int


def _skill(request: Request, skill_id: str) -> dict:
    skill = request.app.state.bank.skill(skill_id)
    if not skill:
        raise HTTPException(404, "המיומנות לא נמצאה")
    return skill


def _run(rows: list[dict]) -> int:
    """Correct answers in a row (up to 3) among the answers that count for mastery."""
    run = 0
    for answer in reversed(last_counted(rows)):
        if not answer["correct"]:
            break
        run += 1
    return run


def _current_question(request: Request, user: dict, skill_id: str, progress: dict | None, rows: list[dict]) -> tuple[dict | None, dict | None]:
    """The question on screen, picked and remembered if there is none. (served question or None when the round is done, progress)
    A student who practised before rounds existed begins a new round: their earlier answers are past rounds."""
    bank, store = request.app.state.bank, request.app.state.store
    keys = bank.practice_keys(skill_id)
    if not keys:
        return None, progress
    start = progress.get("round_start") if progress else None
    rnd = current_round(keys, rows, start)
    if rnd["done"]:
        return None, progress
    key = progress["current_key"] if progress else None
    if key not in rnd["left"] or start is None:
        key = next_in_round(rnd["left"])
        progress = store.save_progress(user["id"], skill_id, current_key=key, current_helped=False,
                                       **({"round_start": len(rows)} if start is None else {}))
    return bank.practice_question(skill_id, key), progress


def _named(bank, ids: list[str]) -> list[dict]:
    return [{"id": i, "name": bank.skill(i)["name"]} for i in ids if bank.skill(i)]


def _round_view(request: Request, skill_id: str, rows: list[dict], round_start: int | None) -> dict:
    """Where the student is in the round: how many answered, a result per answer, and when it is done, how it went (never the right answers)."""
    bank = request.app.state.bank
    keys = bank.practice_keys(skill_id)
    rnd = current_round(keys, rows, round_start)
    results = [r["correct"] for r in rnd["answers"]]
    view = {"total": len(keys), "answered": len(results), "results": results, "done": rnd["done"], "result": None}
    if rnd["done"]:
        missed = []
        for r in rnd["answers"]:
            if r["correct"]:
                continue
            served = bank.practice_question(skill_id, r["question_key"])
            mistake = bank.mistake(r.get("mistake_id"))
            back = bank.skill(mistake["back"]) if mistake and mistake["back"] else None
            missed.append({"question": served["question"] if served else "", "mistake": {"name": mistake["name"], "tip": mistake["tip"]} if mistake else None,
                           "back": {"id": back["id"], "name": back["name"]} if back and back["id"] != skill_id else None})
        view["result"] = {"right": sum(results), "total": len(keys), "missed": missed}
    return view


def visible_lesson_ids(request: Request, user: dict) -> set[str] | None:
    """The lessons the student can see: every lesson once they are in a class, none before. None means all (a teacher or a developer)."""
    if set(user["roles"]) - {"student"}:
        return None
    if not reads.of(request).classes_of_student(user["email"]):
        return set()
    return {lesson["id"] for lesson in request.app.state.bank.lessons}


@router.get("/skills/{skill_id}")
def open_skill(skill_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    bank, here = request.app.state.bank, reads.of(request)
    skill, uid = _skill(request, skill_id), user["id"]
    here.prefetch(("get_progress", uid, skill_id), ("answers_of", uid, skill_id), ("daily_correct", uid))      # one wait for all three
    rows = here.answers_of(uid, skill_id)
    question, progress = _current_question(request, user, skill_id, here.get_progress(uid, skill_id), rows)
    lesson = next(l for l in bank.lessons if l["id"] == skill["unit"])
    return {
        "id": skill_id, "name": skill["name"], "description": skill.get("description", ""),
        "lesson": {"id": lesson["id"], "name": lesson["name"]},
        "state": skill_state(progress), "question": question, "practice_available": bool(bank.question_keys(skill_id)),
        "round": _round_view(request, skill_id, rows, progress.get("round_start") if progress else None),
        "correct_in_row": _run(rows),
        "requires": _named(bank, skill.get("prereqs", [])),
        "opens": _named(bank, [s["id"] for s in bank.skills if skill_id in s.get("prereqs", [])]),
        "help": {"explanation": skill.get("description", ""), "solved_example": skill.get("worked_example")},
        "today": today_progress(here.daily_correct(uid), clock.school_day()),
    }


@router.post("/skills/{skill_id}/help")
def open_help(skill_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """The student opened help for the question on screen: that answer will not count for mastery."""
    _skill(request, skill_id)
    request.app.state.store.save_progress(user["id"], skill_id, current_helped=True)
    return {"ok": True}


def _to_review(store, user_id: str, skill_id: str, key: str) -> None:
    try:
        store.add_review(user_id, [(skill_id, key, "practice")], clock.now())
    except Exception as exc:                                                         # bookkeeping never fails an answer
        log.warning("could not add a wrong answer to the review list: %s", type(exc).__name__)


@router.post("/skills/{skill_id}/answer")
def answer(skill_id: str, body: Answer, request: Request, user: dict = Depends(learner)) -> dict:
    """Grade one practice answer. The waits: the reads together, the answer written, the progress written once."""
    bank, store, here = request.app.state.bank, request.app.state.store, reads.of(request)
    _skill(request, skill_id)
    uid, today, now = user["id"], clock.school_day(), clock.now().isoformat()
    here.prefetch(("get_progress", uid, skill_id), ("answers_of", uid, skill_id), ("daily_correct", uid), ("reward_state", uid))
    progress = here.get_progress(uid, skill_id)
    if not progress or progress["current_key"] != body.question_key:
        raise HTTPException(409, "השאלה הזו כבר לא על המסך")
    graded = bank.grade(skill_id, body.question_key, body.choice)
    if graded is None:
        raise HTTPException(422, "תשובה לא חוקית")

    correct, counted = graded["correct"], not progress["current_helped"]
    mistake_id = graded["mistake"]["id"] if graded["mistake"] else None
    review = None if correct else reads.POOL.submit(_to_review, store, uid, skill_id, body.question_key)         # a wrong answer goes to חזרה, in parallel
    store.add_answer(uid, skill_id, body.question_key, correct, counted, mistake_id, today)
    before = here.answers_of(uid, skill_id)
    rows = before + [{"question_key": body.question_key, "correct": correct, "counted": counted, "day": today, "mistake_id": mistake_id}]
    start = progress.get("round_start")
    if start is None:                                                                   # practised before rounds: this answer begins one
        start = len(before)
    was_mastered = bool(progress.get("mastered_at"))
    mastered_now = not was_mastered and is_mastered(last_counted(rows))
    rnd = current_round(bank.practice_keys(skill_id), rows, start)
    following = next_in_round(rnd["left"], body.question_key)                           # None when the round is done: no question comes back
    changes = {"current_key": following, "current_helped": False, "round_start": start}
    if not progress.get("started_at"):
        changes["started_at"] = now                                                    # a first answer moves a skill out of "not started"
    if mastered_now:
        changes["mastered_at"] = now
    progress = store.save_progress(uid, skill_id, **changes)                           # one write, with everything this answer changed
    if review:
        review.result()

    mistake = graded["mistake"]
    if mistake and mistake["back"]:
        back = bank.skill(mistake["back"])
        mistake = {**mistake, "back_name": back["name"] if back else None}
    daily = dict(here.daily_correct(uid))
    if correct:
        daily[today] = daily.get(today, 0) + 1
    today_now = today_progress(daily, today)
    return {
        "comet": correct and _comet_due(request, uid, today_now, here.reward_state(uid)),
        "correct": correct, "mistake": mistake,
        "state": skill_state(progress), "mastered_now": mastered_now,
        "correct_in_row": _run(rows), "round": _round_view(request, skill_id, rows, start),
        "next_question": bank.practice_question(skill_id, following) if following else None,
        "today": today_now,
    }


@router.post("/skills/{skill_id}/round")
def new_round(skill_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """"סבב חדש": after a finished round, all the skill's practice questions again in a new order. Before the round is done it changes nothing."""
    bank, store, here = request.app.state.bank, request.app.state.store, reads.of(request)
    _skill(request, skill_id)
    uid = user["id"]
    here.prefetch(("get_progress", uid, skill_id), ("answers_of", uid, skill_id))
    keys, rows, progress = bank.practice_keys(skill_id), here.answers_of(uid, skill_id), here.get_progress(uid, skill_id)
    if keys and current_round(keys, rows, progress.get("round_start") if progress else None)["done"]:
        store.save_progress(uid, skill_id, round_start=len(rows), current_key=next_in_round(keys), current_helped=False)
    return {"ok": True}


def _comet_due(request: Request, user_id: str, today_now: dict, state: dict | None) -> bool:
    """After a right answer: does a comet cross? The day is stored at once, so a reload cannot bring a second one. The caught comets are
    read only when one could really be due (the first goal of all, or a lucky roll on a day without one)."""
    store, today = request.app.state.store, clock.school_day()
    roll_of = getattr(request.app.state, "comet_roll", None)
    roll = roll_of() if roll_of else None
    reached_now = today_now["done"] == DAILY_GOAL                 # this answer was the fifth right one of the day
    if comets.surely_not(state, today, reached_now, roll):
        return False
    if not comets.due(state, reads.of(request).comets_of(user_id), today, reached_now, roll if roll is not None else 0.0):
        return False
    store.save_reward_state(user_id, last_comet_day=today)
    return True


@router.get("/path")
def path(request: Request, user: dict = Depends(learner)) -> dict:
    store, here, uid = request.app.state.store, reads.of(request), user["id"]
    here.prefetch(("progress_of", uid), ("last_answered", uid), ("daily_correct", uid), ("recent_skills", uid, RECENT), ("attempts_of", uid, "quiz"), ("curriculum",))
    states = {p["skill_id"]: skill_state(p) for p in here.progress_of(uid)}
    last, today = here.last_answered(uid), clock.school_day()
    quizzes_facts = quiz.facts(store, request.app.state.bank, uid, clock.now(), here)
    shown, dates = visible_lesson_ids(request, user), here.curriculum()
    lessons, order = [], []
    for lesson in request.app.state.bank.lessons_with_skills():
        if shown is not None and lesson["id"] not in shown:
            continue
        skills = [{"id": s["id"], "name": s["name"], "short": s["short"], "state": states.get(s["id"], "not_started"),
                   "faded": is_faded(states.get(s["id"], "not_started"), last.get(s["id"]), today)}
                  for s in lesson["skills"]]
        order += [s["id"] for s in skills]
        mastered = sum(1 for s in skills if s["state"] == MASTERED)
        fact = quizzes_facts.get(lesson["id"], {})
        passed = bool(fact.get("passed"))
        completed = passed or (bool(skills) and mastered == len(skills))
        due = dates.get(lesson["id"])
        lessons.append({"id": lesson["id"], "name": lesson["name"], "skills": skills, "mastered": mastered,
                        "completed": completed, "passed": passed, "due_date": due.isoformat() if due else None,
                        "behind": bool(due and due < today and not completed),
                        "quiz": {"best": fact.get("best"), "open": bool(fact.get("open")), "due_at": fact["open"]["due_at"].isoformat() if fact.get("open") else None}})
    daily = here.daily_correct(uid)
    return {"lessons": lessons, "behind": sum(1 for l in lessons if l["behind"]), "next": next_skill(order, states, here.recent_skills(uid, RECENT)),
            "today": today_progress(daily, today), "streak": streak(daily, today)}


@router.get("/collection")
def collection(request: Request, user: dict = Depends(learner)) -> dict:
    bank, here, uid = request.app.state.bank, reads.of(request), user["id"]
    here.prefetch(("progress_of", uid), ("last_answered", uid))
    mastered_at = {p["skill_id"]: p["mastered_at"] for p in here.progress_of(uid) if p.get("mastered_at")}
    names = {lesson["id"]: lesson["name"] for lesson in bank.lessons}
    last, today = here.last_answered(uid), clock.school_day()
    skills = [{"id": s["id"], "name": s["name"], "lesson_id": s["unit"], "lesson_name": names[s["unit"]],
               "mastered_at": mastered_at[s["id"]], "faded": is_faded(MASTERED, last.get(s["id"]), today)}
              for s in bank.skills if s["id"] in mastered_at]
    lessons = []
    for lesson in bank.lessons:
        ids = [s["id"] for s in bank.skills if s["unit"] == lesson["id"]]
        if ids and all(i in mastered_at for i in ids):
            lessons.append({"id": lesson["id"], "name": lesson["name"], "skills": len(ids)})
    return {"skills": skills, "lessons": lessons}


@router.get("/comets")
def comet_list(request: Request, user: dict = Depends(learner)) -> dict:
    """The twelve comets: the ones the student caught come with their symbol, name and fact; the others only their place."""
    caught = request.app.state.store.comets_of(user["id"])
    return {"comets": [{**c, "caught": True} if c["id"] in caught else {"id": c["id"], "caught": False} for c in comets.COMETS],
            "caught": len(caught), "total": len(comets.COMETS)}


@router.post("/comets/catch")
def comet_catch(request: Request, user: dict = Depends(learner)) -> dict:
    """Catch the comet that crossed today: one catch per crossing, a comet the student does not have, picked by the server."""
    store, today = request.app.state.store, clock.school_day()
    state = store.reward_state(user["id"]) or {}
    if state.get("last_comet_day") != today or state.get("last_catch_day") == today:
        raise HTTPException(409, "אין שביט לתפוס")
    roll = getattr(request.app.state, "comet_roll", None)
    comet = comets.pick(store.comets_of(user["id"]), roll() if roll else None)
    if comet is None:
        raise HTTPException(409, "אין שביט לתפוס")
    store.add_comet(user["id"], comet["id"])
    store.save_reward_state(user["id"], last_catch_day=today)
    return {"comet": comet}
