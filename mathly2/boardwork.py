"""The work on the board (הדרך): every answer keeps a picture of the student's board for its question, so a teacher can grade the way and not
only the final answer.

The browser sends the picture when the student answers (practice, a lesson round) or chooses (a quiz, an exercise test, the simulation), and
again before handing in when the board changed. One picture is kept per student, attempt (or "practice") and question; the one it replaces is
left with nothing referring to it, and the hourly cleanup removes it. In a graded attempt (a lesson quiz, an exercise test, the simulation) the
teacher of the student's class sees each question with the student's choice and board, and can give it 0, half or full points for the work;
the attempt's grade is recomputed."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from . import attempts, clock, pictures
from .access import allowed, learner, need
from .written import picture_error

router = APIRouter(prefix="/api")

PRACTICE = "practice"
GRADED = ("quiz", "exercise_test", "simulation")        # the attempts whose work a teacher grades
LATE_UPLOAD = timedelta(minutes=10)                     # a hand-in waits for the last pictures; after this an attempt's work is closed
WORK_REQUIRED = GRADED                                  # the browser asks for work on the board before a choice in these


def _skill_of_key(bank, key: str) -> str | None:
    """The skill a bank question key belongs to (a key starts with its skill's id)."""
    for skill in bank.skills:
        if key.startswith(skill["id"]) and key in bank.question_keys(skill["id"]):
            return skill["id"]
    return None


@router.post("/work", status_code=201)
async def upload_work(request: Request, ref: str = Query(..., max_length=64), key: str = Query(..., max_length=200),
                      user: dict = Depends(learner)) -> dict:
    """The student's board for one answer, as a picture (raw image bytes). `ref`: the attempt's id, or "practice"."""
    store, bank = request.app.state.store, request.app.state.bank
    if ref == PRACTICE:
        skill_id = _skill_of_key(bank, key)
    else:
        row = store.get_attempt(ref)
        if row is None or row["user_id"] != user["id"]:
            raise HTTPException(404, "הבוחן לא נמצא")
        if not attempts.is_open(row) and clock.now() - row["submitted_at"] > LATE_UPLOAD:
            raise HTTPException(409, "הבוחן כבר הוגש")
        skill_id = next((q["skill_id"] for q in row["questions"] if q["key"] == key), None)
    if skill_id is None:
        raise HTTPException(404, "השאלה לא נמצאה")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > pictures.MAX_IMAGE + 1024:
        raise picture_error(pictures.PictureError(413, "image_too_large"))
    data, kind = await request.body(), request.headers.get("content-type", "")

    def work() -> dict:
        jpeg = pictures.clean_image(data, kind)
        saved = pictures.store_picture(store, request.app.state.pictures, user["id"], "work", jpeg)
        store.save_work(user["id"], ref, key, skill_id, saved["id"], clock.now())
        return saved
    try:
        row = await run_in_threadpool(work)
    except pictures.PictureError as exc:
        raise picture_error(exc) from exc
    return {"id": row["id"]}


# ---- the teacher: graded attempts with their work, and points for the way ----

def _taught(request: Request, user: dict) -> list[dict]:
    store = request.app.state.store
    return store.classes() if allowed(user["roles"], "*") else store.classes_taught(user["email"])


def teaches_student(request: Request, user: dict, student_id: str) -> bool:
    """Is the caller a teacher of a class this student is in (or a developer)?"""
    if allowed(user["roles"], "*"):
        return True
    store = request.app.state.store
    return any(m["user_id"] == student_id for c in store.classes_taught(user["email"]) for m in store.members(c["id"]))


def _title(request: Request, row: dict) -> str:
    bank, store = request.app.state.bank, request.app.state.store
    if row["kind"] == "quiz":
        return "בוחן: " + next((l["name"] for l in bank.lessons if l["id"] == row["scope"]), row["scope"])
    test_id, _, number = row["scope"].partition(":")
    test = store.get_test(int(test_id)) if test_id.isdigit() else None
    when = f" ({test['date'].day}.{test['date'].month})" if test else ""
    return (f"מבחן תרגול {number}" if row["kind"] == "exercise_test" else "מבחן סימולציה") + when


def _iso(value):
    return value.isoformat() if value else None


@router.get("/teaching/work")
def work_list(request: Request, user: dict = Depends(need("class.teach"))) -> list[dict]:
    """The handed-in quizzes and tests of the teacher's students, the ones not checked yet first, then the newest."""
    store, items, seen = request.app.state.store, [], set()
    for klass in _taught(request, user):
        emails = {m["user_id"]: m["email"] for m in store.members(klass["id"]) if m["user_id"]}
        for kind in GRADED:
            for uid, rows in store.attempts_of_users(list(emails), kind).items():
                for row in rows:
                    if attempts.is_open(row) or row["id"] in seen:
                        continue
                    seen.add(row["id"])
                    items.append({"id": row["id"], "kind": kind, "title": _title(request, row), "student": emails[uid],
                                  "class": {"id": klass["id"], "name": klass["name"]}, "grade": row["grade"],
                                  "submitted_at": _iso(row["submitted_at"]), "checked": bool(row.get("checked_at"))})
    items.sort(key=lambda i: i["submitted_at"] or "", reverse=True)
    return sorted(items, key=lambda i: i["checked"])


def _graded_attempt(request: Request, user: dict, attempt_id: str) -> dict:
    row = request.app.state.store.get_attempt(attempt_id)
    if row is None or row["kind"] not in GRADED or attempts.is_open(row) or not teaches_student(request, user, row["user_id"]):
        raise HTTPException(404, "הבוחן לא נמצא")
    return row


def teacher_view(request: Request, row: dict) -> dict:
    """Every question with its choices (the right one marked: this is the teacher), the student's choice, the automatic points, the
    teacher's credit and the board's picture."""
    bank, store = request.app.state.bank, request.app.state.store
    work = store.work_of(row["user_id"], row["id"])
    questions = []
    for q in row["questions"]:
        served = bank.practice_question(q["skill_id"], q["key"])
        if served is None:
            continue
        choices = [{**c, "correct": bool((bank.grade(q["skill_id"], q["key"], c["index"]) or {}).get("correct"))} for c in served["choices"]]
        picked = row["answers"].get(q["key"])
        questions.append({"key": q["key"], "skill_name": (bank.skill(q["skill_id"]) or {}).get("name", ""),
                          "question": served["question"], **{k: served[k] for k in ("figure", "graph") if k in served},
                          "choices": choices, "picked": picked if isinstance(picked, int) else None,
                          "auto": 1 if any(c["correct"] and c["index"] == picked for c in choices) else 0,
                          "credit": row["credit"].get(q["key"]), "work": work.get(q["key"]),
                          "ai": ((row.get("review") or {}).get("questions") or {}).get(q["key"])})       # the AI's review of the way: a suggestion
    student = next((m["email"] for c in store.classes() for m in store.members(c["id"]) if m["user_id"] == row["user_id"]), "")
    return {"id": row["id"], "kind": row["kind"], "title": _title(request, row), "student": student, "grade": row["grade"],
            "submitted_at": _iso(row["submitted_at"]), "checked_at": _iso(row.get("checked_at")), "checked_by": row.get("checked_by"),
            "questions": questions, "ai_summary": (row.get("review") or {}).get("summary")}


@router.get("/teaching/work/{attempt_id}")
def work_open(attempt_id: str, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    return teacher_view(request, _graded_attempt(request, user, attempt_id))


class Credit(BaseModel):
    credit: dict[str, float | None]


@router.post("/teaching/work/{attempt_id}")
def work_check(attempt_id: str, body: Credit, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    """Points for the way: per question 0, 0.5 or 1 (None: back to the automatic points). The grade is recomputed from all of them."""
    store, bank = request.app.state.store, request.app.state.bank
    row = _graded_attempt(request, user, attempt_id)
    keys = {q["key"] for q in row["questions"]}
    credit = dict(row["credit"])
    for key, value in body.credit.items():
        if key not in keys or (value is not None and value not in attempts.CREDITS):
            raise HTTPException(422, "ניקוד לא תקין")
        if value is None:
            credit.pop(key, None)
        else:
            credit[key] = value
    value, _ = attempts.grade(bank, row["questions"], row["answers"], credit)
    saved = store.save_attempt(row["id"], credit=credit, grade=value, checked_at=clock.now(), checked_by=user["email"])
    return teacher_view(request, saved)
