"""Photographed questions (שאלה מצולמת): a student photographs a question with the phone (the 4-digit code, as for an assignment's answer);
the AI (Gemini, boardreview.GeminiReviewer) reads it, writes its answer and steps (kept for the check, never shown before it), and suggests
its skill or "external". The student sees it like any question, may change the skill, writes the way on the board (and the final answer in a
box when it is a plain number), and hands in; the AI gives a grade 0-100, a verdict and feedback on the way. After its first check the question
waits for the class's teacher, who approves it into the class's bank (fixing its skill or wording) or rejects it; an approved question can be
solved by the class's other students from the same sheet ("שאלות מהכיתה").

A student photographs at most DAILY_LIMIT questions a day and hands in each at most CHECKS times. Without the AI key there is no reading:
the feature says it is not available. Nothing here sends a name or an email to the AI: the photo, the question and the skills' names only."""
from __future__ import annotations

import logging
import threading
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import clock, writtentest
from .access import allowed, learner, my_classes, need

log = logging.getLogger("mathly2.photoq")
router = APIRouter(prefix="/api")

DAILY_LIMIT = 5
CHECKS = 3
REF = "pq:"                                   # board work's ref for a photographed question (boardwork.py)
KEY = "q"
REASONS = {"unreadable": "לא הצלחנו לקרוא שאלה בתמונה. צלמו שוב: שאלה אחת, ישר, מקרוב ובאור טוב.",
           "no_ai": "צילום שאלות לא זמין כרגע (אין חיבור לבינה המלאכותית).",
           "failed": "לא הצלחנו לקרוא את השאלה הפעם. נסו שוב בעוד רגע.",
           "check_failed": "לא הצלחנו לבדוק את הפתרון הפעם. אפשר להגיש שוב."}


def reviewer(request_or_app):
    app = getattr(request_or_app, "app", request_or_app)
    return getattr(app.state, "reviewer", None)


def _run(app, target, *args) -> None:
    runner = getattr(app.state, "run_photoq", None)
    if runner:                                # tests: inline
        runner(target, app, *args)
    else:
        threading.Thread(target=target, args=(app, *args), name="photo-question", daemon=True).start()


def subject_skills(bank, subject: str, lesson_ids: set[str] | None) -> list[dict]:
    """The skills a photographed question of this subject can be classified under (the student's lessons)."""
    lessons = [l for l in bank.lessons_of_subject(subject) if lesson_ids is None or l["id"] in lesson_ids]
    units = {l["id"] for l in lessons}
    return [{"id": s["id"], "name": s["name"]} for s in bank.skills if s["unit"] in units]


def final_box(answer: str) -> dict | None:
    """A box for the final answer when the AI's answer is a plain number (as in the written simulation)."""
    ref = {"skill_id": "", "key": ""}
    fake = type("B", (), {"practice_question": lambda self, s, k: {"choices": [{"index": 0, "text": answer}]},
                          "grade": lambda self, s, k, i: {"correct": True}})()
    found = writtentest.final_of(fake, ref) if answer else None
    return {"label": found["label"], "unit": found["unit"]} if found else None


# ---- the background work ----

def read_job(app, question_id: str) -> None:
    """Read the photo: the question, its answer and steps, and the suggested skill; or unreadable / failed. Never raises."""
    store = app.state.store
    row = store.get_photo_question(question_id)
    try:
        picture = store.get_picture(row["picture_id"])
        image = app.state.pictures.get(picture["path"])
        skills = subject_skills(app.state.bank, row["subject_id"], None)
        got = reviewer(app).read_question(image, skills, next((s["name"] for s in app.state.bank.subjects if s["id"] == row["subject_id"]), ""))
        if not got.get("readable") or not str(got.get("question", "")).strip():
            store.save_photo_question(question_id, state="unreadable", reason="unreadable")
            return
        ids = {s["id"] for s in skills}
        skill = got.get("skill") if got.get("skill") in ids else None
        store.save_photo_question(question_id, state="ready", question=str(got["question"])[:4000], answer=str(got.get("answer", ""))[:1000],
                                  steps=[str(x)[:400] for x in (got.get("steps") or [])][:8], suggested_skill=skill, skill_id=skill)
    except Exception as exc:
        log.warning("reading a photographed question failed: %s", getattr(exc, "reason", type(exc).__name__))
        try:
            store.save_photo_question(question_id, state="failed", reason="failed")
        except Exception:
            log.exception("could not save the failure")


def check_job(app, question_id: str) -> None:
    """Grade the board: 0-100, the verdict and the feedback. The first check of a photographed question sends it to the teacher."""
    store = app.state.store
    row = store.get_photo_question(question_id)
    try:
        work = store.work_of(row["user_id"], REF + row["id"])
        picture = store.get_picture(work[KEY])
        board = app.state.pictures.get(picture["path"])
        got = reviewer(app).grade_open(row["question"], row["answer"], row["typed"] or None, board)
        score = max(0, min(100, int(got.get("score", 0))))
        verdict = got.get("verdict") if got.get("verdict") in ("correct", "partial", "wrong", "unclear") else "unclear"
        fields = {"state": "checked", "grade": score, "checked_at": clock.now(), "reason": None,
                  "review": {"verdict": verdict, "feedback": str(got.get("feedback", ""))[:600], "tip": str(got.get("tip", ""))[:300],
                             "checks": _checks(row)}}
        if row["picture_id"] and row["bank"] == "none" and row["class_id"]:
            fields["bank"] = "pending"                                       # the teacher decides whether it joins the class's bank
        store.save_photo_question(question_id, **fields)
    except Exception as exc:
        log.warning("checking a photographed question failed: %s", getattr(exc, "reason", type(exc).__name__))
        try:
            store.save_photo_question(question_id, state="ready", reason="check_failed")
        except Exception:
            log.exception("could not save the failure")


# ---- what the student sees ----

def _checks(row: dict) -> int:
    return int((row.get("review") or {}).get("checks", 0)) if isinstance(row.get("review"), dict) else 0


def student_view(request: Request, row: dict, user: dict) -> dict:
    """A question as its student sees it: the answer and the steps only after the check."""
    bank = request.app.state.bank
    from .skills import visible_lesson_ids
    skills = subject_skills(bank, row["subject_id"], visible_lesson_ids(request, user))
    checked = row["state"] == "checked"
    names = {s["id"]: s["name"] for s in bank.skills}
    out = {"id": row["id"], "state": row["state"], "question": row["question"], "picture_id": row["picture_id"], "subject_id": row["subject_id"],
           "suggested_skill": row["suggested_skill"], "skill": {"id": row["skill_id"], "name": names.get(row["skill_id"], "")} if row["skill_id"] else None,
           "skills": skills, "final": final_box(row["answer"]) if row["state"] in ("ready", "checking", "checked") else None,
           "typed": row["typed"], "grade": row["grade"], "review": row["review"] if checked else None, "bank": row["bank"],
           "from_bank": bool(row["source_id"]), "checks_left": max(0, CHECKS - _checks(row)),
           "reason": REASONS.get(row["reason"]) if row["reason"] else None, "created_at": row["created_at"].isoformat() if row["created_at"] else None}
    if checked:
        out["answer"], out["steps"] = row["answer"], row["steps"]
    return out


def _mine(request: Request, user: dict, question_id: str) -> dict:
    row = request.app.state.store.get_photo_question(question_id)
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(404, "השאלה לא נמצאה")
    return row


class NewQuestion(BaseModel):
    picture_id: str = Field(..., max_length=64)
    subject: str = Field("math", max_length=40)


class HandIn(BaseModel):
    skill_id: str | None = Field(None, max_length=80)                # None or "": external
    typed: str = Field("", max_length=40)


@router.get("/photo-questions")
def my_questions(request: Request, user: dict = Depends(learner), subject: str = "math") -> dict:
    """The student's photographed questions (the newest first), the class's bank (approved, not their own), and whether the AI is on."""
    store = request.app.state.store
    mine = [r for r in store.photo_questions_of(user["id"]) if r["subject_id"] == subject]
    class_ids = [c["id"] for c in my_classes(request, user)]
    solved = {r["source_id"] for r in mine if r["source_id"]}
    approved = [r for r in store.photo_questions_of_classes(class_ids, "approved") if r["user_id"] != user["id"] and r["subject_id"] == subject]
    names = {s["id"]: s["name"] for s in request.app.state.bank.skills}
    brief = lambda r: {"id": r["id"], "question": r["question"][:160], "state": r["state"], "grade": r["grade"], "bank": r["bank"],
                       "skill": names.get(r["skill_id"], "") if r["skill_id"] else "", "solved": r["id"] in solved}
    since = clock.now() - timedelta(days=1)
    return {"on": reviewer(request) is not None, "left_today": max(0, DAILY_LIMIT - store.photo_question_count_since(user["id"], since)),
            "mine": [brief(r) for r in mine[:20]], "bank": [brief(r) for r in approved[:30]]}


@router.post("/photo-questions", status_code=201)
def new_question(body: NewQuestion, request: Request, user: dict = Depends(learner)) -> dict:
    """A photo arrived (from the phone's code request, or this device): read it in the background."""
    store = request.app.state.store
    if reviewer(request) is None:
        raise HTTPException(503, REASONS["no_ai"])
    picture = store.get_picture(body.picture_id)
    if picture is None or picture["owner_id"] != user["id"] or picture["deleted_at"]:
        raise HTTPException(404, "התמונה לא נמצאה")
    if store.photo_question_count_since(user["id"], clock.now() - timedelta(days=1)) >= DAILY_LIMIT:
        raise HTTPException(429, f"אפשר לצלם עד {DAILY_LIMIT} שאלות ביום. נמשיך מחר!")
    from .skills import subject_param
    subject = subject_param(request, user, body.subject)
    classes = my_classes(request, user)
    row = store.create_photo_question(user["id"], clock.now(), class_id=classes[0]["id"] if classes else None, subject_id=subject,
                                      picture_id=picture["id"])
    _run(request.app, read_job, row["id"])
    return student_view(request, store.get_photo_question(row["id"]), user)


@router.post("/photo-questions/from-bank/{question_id}", status_code=201)
def from_bank(question_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """Solve a question of the class's bank: a copy of it of one's own, ready for the board."""
    store = request.app.state.store
    source = store.get_photo_question(question_id)
    class_ids = {c["id"] for c in my_classes(request, user)}
    if source is None or source["bank"] != "approved" or source["class_id"] not in class_ids:
        raise HTTPException(404, "השאלה לא נמצאה")
    if reviewer(request) is None:
        raise HTTPException(503, REASONS["no_ai"])
    row = store.create_photo_question(user["id"], clock.now(), class_id=source["class_id"], subject_id=source["subject_id"], source_id=source["id"],
                                      state="ready", question=source["question"], answer=source["answer"], steps=source["steps"],
                                      suggested_skill=source["skill_id"], skill_id=source["skill_id"])
    return student_view(request, row, user)


@router.get("/photo-questions/{question_id}")
def read_question(question_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    return student_view(request, _mine(request, user, question_id), user)


@router.post("/photo-questions/{question_id}/submit")
def hand_in(question_id: str, body: HandIn, request: Request, user: dict = Depends(learner)) -> dict:
    """The board is in (boardwork.py, ref pq:<id>): keep the chosen skill and the typed answer, and check it in the background."""
    store = request.app.state.store
    row = _mine(request, user, question_id)
    if row["state"] not in ("ready", "checked"):
        raise HTTPException(409, "השאלה עוד לא מוכנה" if row["state"] == "reading" else "השאלה כבר נבדקת" if row["state"] == "checking" else "אי אפשר להגיש את השאלה הזו")
    if _checks(row) >= CHECKS:
        raise HTTPException(409, f"הגשתם את השאלה הזו {CHECKS} פעמים. נסו שאלה אחרת!")
    if reviewer(request) is None:
        raise HTTPException(503, REASONS["no_ai"])
    if KEY not in store.work_of(user["id"], REF + row["id"]):
        raise HTTPException(422, "קודם כותבים את הפתרון בלוח")
    skill = body.skill_id or None
    if skill is not None:
        from .skills import visible_lesson_ids
        if skill not in {s["id"] for s in subject_skills(request.app.state.bank, row["subject_id"], visible_lesson_ids(request, user))}:
            raise HTTPException(422, "מיומנות לא מוכרת")
    review = {**(row["review"] or {}), "checks": _checks(row) + 1}
    store.save_photo_question(row["id"], state="checking", skill_id=skill, typed=body.typed.strip(), review=review, reason=None)
    _run(request.app, check_job, row["id"])
    return student_view(request, store.get_photo_question(row["id"]), user)


# ---- the teacher: approve into the class's bank ----

class Decision(BaseModel):
    action: Literal["approve", "reject", "pending"]
    skill_id: str | None = Field(None, max_length=80)
    question: str | None = Field(None, max_length=4000)
    answer: str | None = Field(None, max_length=1000)


def _taught_ids(request: Request, user: dict) -> list[int]:
    store = request.app.state.store
    classes = store.classes() if allowed(user["roles"], "*") else store.classes_taught(user["email"])
    return [c["id"] for c in classes]


def teacher_view(request: Request, row: dict, emails: dict[str, str]) -> dict:
    store, bank = request.app.state.store, request.app.state.bank
    names = {s["id"]: s["name"] for s in bank.skills}
    work = store.work_of(row["user_id"], REF + row["id"])
    return {"id": row["id"], "student": emails.get(row["user_id"], ""), "class_id": row["class_id"], "question": row["question"], "answer": row["answer"],
            "steps": row["steps"], "picture_id": row["picture_id"], "board_id": work.get(KEY), "suggested_skill": row["suggested_skill"],
            "skill": {"id": row["skill_id"], "name": names.get(row["skill_id"], "")} if row["skill_id"] else None, "grade": row["grade"],
            "review": row["review"], "bank": row["bank"], "skills": subject_skills(bank, row["subject_id"], None),
            "created_at": row["created_at"].isoformat() if row["created_at"] else None}


@router.get("/teaching/photo-questions")
def teaching_questions(request: Request, user: dict = Depends(need("class.teach")), bank: str = "pending") -> list[dict]:
    """The classes' photographed questions waiting for a decision (or approved / rejected)."""
    if bank not in ("pending", "approved", "rejected"):
        raise HTTPException(422, "סינון לא מוכר")
    store = request.app.state.store
    ids = _taught_ids(request, user)
    emails = {m["user_id"]: m["email"] for i in ids for m in store.members(i) if m.get("user_id")}
    return [teacher_view(request, r, emails) for r in store.photo_questions_of_classes(ids, bank)]


@router.post("/teaching/photo-questions/{question_id}")
def decide(question_id: str, body: Decision, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    store = request.app.state.store
    row = store.get_photo_question(question_id)
    if row is None or row["class_id"] not in _taught_ids(request, user) or row["source_id"]:
        raise HTTPException(404, "השאלה לא נמצאה")
    fields: dict = {"bank": {"approve": "approved", "reject": "rejected", "pending": "pending"}[body.action], "decided_by": user["email"],
                    "decided_at": clock.now()}
    if body.skill_id is not None:
        if body.skill_id and body.skill_id not in {s["id"] for s in subject_skills(request.app.state.bank, row["subject_id"], None)}:
            raise HTTPException(422, "מיומנות לא מוכרת")
        fields["skill_id"] = body.skill_id or None
    if body.question is not None and body.question.strip():
        fields["question"] = body.question.strip()
    if body.answer is not None and body.answer.strip():
        fields["answer"] = body.answer.strip()
    saved = store.save_photo_question(row["id"], **fields)
    emails = {m["user_id"]: m["email"] for m in store.members(row["class_id"]) if m.get("user_id")}
    return teacher_view(request, saved, emails)
