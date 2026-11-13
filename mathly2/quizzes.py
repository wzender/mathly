"""Lesson quizzes and attempts: start a quiz, save answers, submit, read the result, list the grades. The server keeps the timer,
draws the questions and grades; it never says which choice was right."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from . import attempts, clock, quiz, reads
from .access import learner
from .skills import visible_lesson_ids

router = APIRouter(prefix="/api")


class AnswerBody(BaseModel):
    key: str
    choice: int


def _lesson(request: Request, user: dict, lesson_id: str) -> dict:
    lesson = next((l for l in request.app.state.bank.lessons if l["id"] == lesson_id), None)
    shown = visible_lesson_ids(request, user)
    if lesson is None or (shown is not None and lesson_id not in shown):
        raise HTTPException(404, "השיעור לא נמצא")
    return lesson


def _lesson_name(request: Request, lesson_id: str) -> str:
    return next((l["name"] for l in request.app.state.bank.lessons if l["id"] == lesson_id), lesson_id)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def _test_info(request: Request, row: dict) -> dict:
    """For an exercise test or a simulation: which real test it belongs to (and which exercise test)."""
    test_id, _, number = row["scope"].partition(":")
    test = request.app.state.store.get_test(int(test_id)) if test_id.isdigit() else None
    names = [l["name"] for l in request.app.state.bank.lessons if test and l["id"] in test["lessons"]]
    return {"id": int(test_id) if test_id.isdigit() else None, "number": int(number) if number.isdigit() else None,
            "date": test["date"].isoformat() if test else None, "lessons": names, "minutes": test["minutes"] if test else None}


def view(request: Request, row: dict) -> dict:
    """An open attempt: its questions (without right answers), the saved answers and the server's clock. A submitted one: its result.
    A quiz carries its `lesson`; an exercise test or a simulation carries its `test`."""
    bank = request.app.state.bank
    base = {"id": row["id"], "kind": row["kind"]}
    if row["kind"] == "quiz":
        base["lesson"] = {"id": row["scope"], "name": _lesson_name(request, row["scope"])}
    else:
        base["test"] = _test_info(request, row)
    if attempts.is_open(row):
        questions = [q for q in (bank.practice_question(r["skill_id"], r["key"]) for r in row["questions"]) if q]
        return {**base, "state": "open", "due_at": _iso(row["due_at"]) if attempts.is_timed(row) else None, "now": _iso(clock.now()), "answers": row["answers"], "questions": questions}
    result = attempts.result(bank, row)
    result.pop("lesson", None)
    return {**base, "state": "submitted", **result, "submitted_at": _iso(row["submitted_at"])}


_view = view


def _mine(request: Request, user: dict, attempt_id: str) -> dict:
    store = request.app.state.store
    row = store.get_attempt(attempt_id)
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(404, "הבוחן לא נמצא")
    return attempts.settle(store, request.app.state.bank, row, clock.now())


@router.get("/lessons/{lesson_id}/quiz")
def quiz_facts(lesson_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    lesson = _lesson(request, user, lesson_id)
    found = quiz.facts(request.app.state.store, request.app.state.bank, user["id"], clock.now()).get(lesson_id, {})
    open_ = found.get("open")
    return {"lesson": {"id": lesson["id"], "name": lesson["name"]}, "subject_id": lesson.get("subject_id", "math"), "best": found.get("best"), "attempts": found.get("attempts", 0),
            "open": {"id": open_["id"], "due_at": _iso(open_["due_at"])} if open_ else None,
            "size": attempts.QUIZ_SIZE, "minutes": None}                                # a quiz has no time limit


@router.post("/lessons/{lesson_id}/quiz/start")
def quiz_start(lesson_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """Resume the open attempt of this lesson if there is one, otherwise draw a new quiz and start the clock."""
    _lesson(request, user, lesson_id)
    store, bank, now = request.app.state.store, request.app.state.bank, clock.now()
    mine = [attempts.settle(store, bank, r, now) for r in store.attempts_of(user["id"], "quiz", lesson_id)]
    for row in mine:
        if attempts.is_open(row):
            return _view(request, row)
    used = Counter(q["key"] for row in mine for q in row["questions"])
    drawn = quiz.draw(bank, lesson_id, used, getattr(request.app.state, "quiz_rng", None))
    if not drawn:
        raise HTTPException(409, "אין עדיין שאלות לבוחן בשיעור הזה")
    row = store.create_attempt(user["id"], "quiz", lesson_id, now, now + timedelta(minutes=attempts.QUIZ_MINUTES), drawn)
    return _view(request, row)


@router.get("/attempts/{attempt_id}")
def attempt_read(attempt_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    return _view(request, _mine(request, user, attempt_id))


@router.put("/attempts/{attempt_id}/answers")
def attempt_answer(attempt_id: str, body: AnswerBody, request: Request, user: dict = Depends(learner)) -> dict:
    store, bank = request.app.state.store, request.app.state.bank
    row = _mine(request, user, attempt_id)
    if not attempts.is_open(row):
        raise HTTPException(409, "הזמן נגמר והבוחן הוגש")
    ref = next((q for q in row["questions"] if q["key"] == body.key), None)
    if ref is None or bank.grade(ref["skill_id"], body.key, body.choice) is None:
        raise HTTPException(422, "תשובה לא חוקית")
    saved = store.save_open_answers(row["id"], {**row["answers"], body.key: body.choice})
    if saved is None:                                    # submitted between the read and the save: the answer came too late
        raise HTTPException(409, "הזמן נגמר והבוחן הוגש")
    return {"saved": len(saved["answers"]), "of": len(saved["questions"])}


@router.post("/attempts/{attempt_id}/submit")
def attempt_submit(attempt_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    row = _mine(request, user, attempt_id)
    row = attempts.submit(request.app.state.store, request.app.state.bank, row, clock.now())
    return _view(request, row)


def _test_ref(request: Request, test: dict) -> dict:
    names = [l["name"] for l in request.app.state.bank.lessons if l["id"] in test["lessons"]]
    return {"id": test["id"], "date": test["date"].isoformat(), "lessons": names, "removed": bool(test["removed_at"])}


@router.get("/grades")
def grades(request: Request, user: dict = Depends(learner), subject: str = Query("math", max_length=40)) -> dict:
    """Every grade the student has: each lesson's best quiz grade, each real test's exercise tests (best of each) and its simulation.
    A removed test keeps its row, so the grades already earned stay."""
    store, bank, now, here, uid = request.app.state.store, request.app.state.bank, clock.now(), reads.of(request), user["id"]
    from .skills import subject_param
    subject = subject_param(request, user, subject)
    here.prefetch(("attempts_of", uid, "quiz"), ("attempts_of", uid, "exercise_test"), ("attempts_of", uid, "simulation"))      # one wait
    found = quiz.facts(store, bank, uid, now, here)
    lessons = []
    for lesson in bank.lessons_of_subject(subject):
        item = found.get(lesson["id"])
        if item and item["best"] is not None:
            lessons.append({"lesson": {"id": lesson["id"], "name": lesson["name"]}, "best": item["best"], "attempts": item["attempts"],
                            "last": _iso(item["last"])})
    groups: dict[tuple[str, str], list[dict]] = {}
    for kind in ("exercise_test", "simulation"):
        for row in here.attempts_of(uid, kind):
            row = attempts.settle(store, bank, row, now)
            if not attempts.is_open(row):
                groups.setdefault((kind, row["scope"]), []).append(row)
    exercise, simulations = [], []
    for (kind, scope), rows in groups.items():
        test_id, _, number = scope.partition(":")
        test = store.get_test(int(test_id)) if test_id.isdigit() else None
        if test is None or test.get("subject_id", "math") != subject:
            continue
        item = {"test": _test_ref(request, test), "best": max(r["grade"] for r in rows), "attempts": len(rows),
                "last": _iso(max(r["submitted_at"] for r in rows))}
        if kind == "exercise_test":
            exercise.append({**item, "number": int(number)})
        else:
            simulations.append(item)
    exercise.sort(key=lambda g: (g["test"]["date"], g["test"]["id"], g["number"]))
    simulations.sort(key=lambda g: (g["test"]["date"], g["test"]["id"]))
    from .assignments import grade_rows
    return {"quizzes": lessons, "exercise_tests": exercise, "simulations": simulations, "assignments": grade_rows(request, user)}
