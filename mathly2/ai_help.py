"""AI help (PRD 4.15): students never call the AI. A student's photographed problem, or a check of a handed-in answer, is a request in the queue
of the class's teacher, who sends it or declines it. The AI runs in a small background pool, so a send returns at once and a batch does not hold
the page. Budgets are taken in one step before the call and given back when it fails or could not read the picture."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import ai, clock, pictures, reads
from .access import allowed, learner, need
from .assignments import _my_assignment, quiz_view
from .pictures import PictureError
from .realtests import _my_class
from .written import picture_error

log = logging.getLogger("mathly2.ai_help")
router = APIRouter(prefix="/api")

MAX_WAITING = 5            # a student's requests waiting at once
MAX_PHOTOS_A_DAY = 20
MAX_LOOK_AGAIN = 5         # a student's open requests to look again
TEACHER_ALLOWANCE = 3      # a teacher's own AI requests a day
OPEN = ("waiting", "processing")
POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ai")


def _is_staff(user: dict) -> bool:
    return allowed(user["roles"], "class.teach")


def _developer(user: dict) -> bool:
    return allowed(user["roles"], "*")


# ---- what a request looks like ----

def _skill(request: Request, skill_id: str | None) -> dict | None:
    skill = request.app.state.bank.skill(skill_id) if skill_id else None
    return {"id": skill["id"], "name": skill["name"]} if skill else None


def view(request: Request, row: dict, staff: bool = False, emails: dict[str, str] | None = None) -> dict:
    """A request as its student sees it, or (`staff`) as the teacher who sends it and a developer see it, with the failure's cause."""
    store, here = request.app.state.store, reads.of(request)
    klass = here.get_class(row["class_id"]) if row["class_id"] else None
    out = {"id": row["id"], "kind": row["kind"], "state": row["state"], "created_at": row["created_at"].isoformat(), "teacher_note": row["teacher_note"],
           "class": {"id": klass["id"], "name": klass["name"]} if klass else None, "skill": _skill(request, row["skill_id"]), "result": None}
    if staff:
        out["student"] = (emails or {}).get(row["user_id"], "")
    if row["kind"] == "photo":
        picture = store.get_picture(row["picture_id"]) if row["picture_id"] else None
        out["picture"] = {"id": picture["id"]} if picture and not picture["deleted_at"] else None
    else:
        assignment = here.get_assignment(row["assignment_id"])
        out["assignment"] = {"id": row["assignment_id"], "title": assignment["title"] if assignment else ""}
    result = row["result"]
    if row["state"] == "done" and result:
        if row["kind"] == "photo":
            out["result"] = {**result, "skill": _skill(request, result.get("skill"))}
        else:
            keep = ("score", "verdict", "feedback", "next_step") + (("transcription", "solution", "readable", "confident") if staff else ())
            out["result"] = {k: result[k] for k in keep if k in result}
    if row["state"] == "failed":
        failure = row["failure"] or {}
        if staff:
            label, todo = ai.FAILURES.get(failure.get("reason"), ai.FAILURES["provider_error"])
            out["failure"] = {"reason": failure.get("reason"), "label": label, "todo": todo, "detail": failure.get("detail", "")}
        else:
            out["failure"] = {"message": ai.STUDENT_MESSAGE}
    return out


def snapshot_of(request: Request, assignment: dict) -> dict:
    """The question as it is now, kept with a check: later changes to the bank or the assignment do not change an old check. No name, no email."""
    snap = {"title": assignment["title"], "note": assignment["note"], "kind": assignment["kind"]}
    if assignment["kind"] == "quiz":
        snap["quiz"] = quiz_view(request.app.state.bank, assignment["quiz_lesson"])
    return snap


# ---- the budgets and the run ----

def _budget(request: Request, row: dict, sender: dict) -> dict | None:
    """What to take for sending this request: the class's daily checks for a student's request, the teacher's own allowance for their own,
    nothing for a developer's own. Returns {"scope", "cap"}."""
    if row["user_id"] == sender["id"]:
        return None if _developer(sender) else {"scope": f"teacher:{sender['email']}", "cap": TEACHER_ALLOWANCE}
    klass = reads.of(request).get_class(row["class_id"])
    return {"scope": f"class:{row['class_id']}", "cap": klass["ai_daily_checks"] if klass else 0}


def send(request: Request, sender: dict, row: dict) -> dict:
    """Take the budget, mark the request processing and hand it to the pool. Raises an HTTP error that says why it could not."""
    store, app = request.app.state.store, request.app
    if row["state"] not in ("waiting", "failed"):
        raise HTTPException(409, "הבקשה כבר טופלה")
    own = row["user_id"] == sender["id"]
    if not own:
        klass = reads.of(request).get_class(row["class_id"])
        if not klass or not klass["ai_enabled"]:
            raise HTTPException(409, "ה־AI כבוי לכיתה הזו")
    take = _budget(request, row, sender)
    today = clock.school_day()
    if take and not store.take_ai_allowance(take["scope"], today, 1, take["cap"]):
        raise HTTPException(429, "נגמרה המכסה היומית של בדיקות ה־AI" if take["scope"].startswith("class:") else f"נגמרו {TEACHER_ALLOWANCE} בקשות ה־AI האישיות להיום")
    started = store.start_ai_request(row["id"], sender["email"], clock.now())
    if started is None:
        if take:
            store.give_back_ai_allowance(take["scope"], today, 1)
        raise HTTPException(409, "הבקשה כבר טופלה")
    if take:
        started = store.save_ai_request(row["id"], budget={"scope": take["scope"], "day": today.isoformat(), "n": 1})
    POOL.submit(run, app, row["id"])
    return started


def _give_back(store, row: dict) -> None:
    b = row.get("budget")
    if b:
        store.give_back_ai_allowance(b["scope"], datetime.fromisoformat(b["day"]).date(), b["n"])
        store.save_ai_request(row["id"], budget=None)


def _delete_photo(app, row: dict) -> None:
    pic = app.state.store.get_picture(row["picture_id"]) if row.get("picture_id") else None
    if pic and not pic["deleted_at"]:
        try:
            pictures.remove_picture(app.state.store, app.state.pictures, pic, clock.now())
        except PictureError as exc:
            log.warning("could not delete a help photo (%s)", exc.code)


def run(app, request_id: str) -> None:
    """The AI call for one processing request, in the pool. It always leaves the request done or failed."""
    store, bank = app.state.store, app.state.bank
    row = store.get_ai_request(request_id)
    if row is None or row["state"] != "processing":
        return
    try:
        if row["kind"] == "photo":
            pic = store.get_picture(row["picture_id"])
            if pic is None or pic["deleted_at"]:
                raise ai.AIFailure("bad_request", "the photo is gone")
            result = app.state.ai.solve(app.state.pictures.get(pic["path"]), "image/jpeg", [{"id": s["id"], "name": s["name"]} for s in bank.skills])
            unreadable = not result.get("readable")
        else:
            images = _check_images(app, row)
            result = app.state.ai.check(images, row["snapshot"] or {})
            unreadable = result.get("verdict") in ("unreadable", "needs_review")
        usage = result.pop("usage", None)
        store.save_ai_request(request_id, state="done", result=result, done_at=clock.now())
        if unreadable:
            _give_back(store, row)                              # a picture the AI could not read does not use the budget
        if row["kind"] == "photo":
            _delete_photo(app, row)                             # the photo is not kept
        _record(app, row, usage)
    except ai.AIFailure as exc:
        _fail(store, row, exc.reason, exc.detail)
    except Exception as exc:                                    # never leave a request processing
        log.exception("AI run failed")
        _fail(store, row, "provider_error", type(exc).__name__)


def _fail(store, row: dict, reason: str, detail: str) -> None:
    store.save_ai_request(row["id"], state="failed", failure={"reason": reason, "detail": detail[:300]}, done_at=clock.now())
    _give_back(store, row)


def _record(app, row: dict, usage: dict | None) -> None:
    if not usage:
        return
    try:
        app.state.store.add_ai_usage(ai.usage_row(usage, "photo" if row["kind"] == "photo" else "check", row["id"], row["user_id"]))
    except Exception as exc:                                    # bookkeeping never fails a request
        log.warning("AI usage not saved: %s", type(exc).__name__)


def _check_images(app, row: dict) -> list[tuple[str, bytes]]:
    store, backend = app.state.store, app.state.pictures
    assignment, sub = store.get_assignment(row["assignment_id"]), store.get_submission(row["assignment_id"], row["user_id"])
    if assignment is None or sub is None:
        raise ai.AIFailure("bad_request", "the answer is gone")
    images: list[tuple[str, bytes]] = []
    ids = [("דפי המטלה", p) for p in assignment["pages"]] + [("תשובת התלמיד", p) for p in sub["pictures"]]
    for label, pid in ids:
        pic = store.get_picture(pid)
        if pic is None or pic["deleted_at"]:
            if label == "תשובת התלמיד":
                raise ai.AIFailure("bad_request", "the answer pictures were deleted")
            continue
        images.append((label, backend.get(pic["path"])))
    return images


def requeue_after_restart(store) -> int:
    try:
        return store.requeue_processing_ai_requests()
    except Exception as exc:                                    # the AI tables may not be migrated yet
        log.warning("could not requeue AI requests: %s", type(exc).__name__)
        return 0


# ---- the student ----

def _student_classes(request: Request, user: dict) -> list[dict]:
    return reads.of(request).classes_of_student(user["email"])


def _choose_class(request: Request, user: dict, wanted: int | None) -> dict:
    """The class whose teacher gets the request: the one asked for, else the nearest coming test, else the one used last, else the first.
    Only a class with the AI on can be chosen."""
    store, today = request.app.state.store, clock.school_day()
    on = [c for c in _student_classes(request, user) if c["ai_enabled"]]
    if not on:
        raise HTTPException(409, "ה־AI לא פועל בכיתה שלך")
    if wanted is not None:
        found = next((c for c in on if c["id"] == wanted), None)
        if found is None:
            raise HTTPException(409, "ה־AI כבוי בכיתה הזו")
        return found
    soonest = {}
    for c in on:
        days = [(t["date"] - today).days for t in store.tests_of_classes([c["id"]]) if t["date"] >= today]
        if days:
            soonest[c["id"]] = min(days)
    if soonest:
        return next(c for c in on if c["id"] == min(soonest, key=soonest.get))
    last = store.ai_requests(user_id=user["id"])
    used = [r["class_id"] for r in reversed(last) if r["class_id"] in {c["id"] for c in on}]
    return next(c for c in on if c["id"] == used[0]) if used else on[0]


def _check_student_limits(request: Request, user: dict, photo: bool) -> None:
    mine = request.app.state.store.ai_requests(user_id=user["id"])
    if sum(1 for r in mine if r["state"] == "waiting" and r["kind"] != "again") >= MAX_WAITING:
        raise HTTPException(429, f"יש כבר {MAX_WAITING} בקשות שמחכות למורה. אפשר לבטל אחת או לחכות.")
    today = clock.school_day()
    if photo and sum(1 for r in mine if r["kind"] == "photo" and clock.school_day(r["created_at"]) == today) >= MAX_PHOTOS_A_DAY:
        raise HTTPException(429, f"אפשר לשלוח עד {MAX_PHOTOS_A_DAY} תמונות ביום")


@router.post("/ai/photo", status_code=201)
async def photo(request: Request, class_id: int | None = None, skill_id: str | None = None, user: dict = Depends(learner)) -> dict:
    """A photographed problem (raw image bytes; the Content-Type says which kind). A student's goes to the queue of the class's teacher; a teacher's or
    developer's own is sent at once."""
    staff = _is_staff(user)
    if skill_id and request.app.state.bank.skill(skill_id) is None:
        raise HTTPException(422, "מיומנות לא מוכרת")
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > pictures.MAX_IMAGE + 1024:
        raise picture_error(PictureError(413, "image_too_large"))
    data = await request.body()
    content_type = request.headers.get("content-type", "")

    def work() -> dict:
        store = request.app.state.store
        klass = None
        if not staff:
            klass = _choose_class(request, user, class_id)
            _check_student_limits(request, user, True)
        jpeg = pictures.clean_image(data, content_type)
        pic = pictures.store_picture(store, request.app.state.pictures, user["id"], "help", jpeg)
        row = store.create_ai_request("photo", user["id"], klass["id"] if klass else None, picture_id=pic["id"], skill_id=skill_id, created_at=clock.now())
        if staff:
            try:
                row = send(request, user, row)                       # their own request goes straight out
            except HTTPException:
                store.save_ai_request(row["id"], state="cancelled")
                _delete_photo(request.app, row)
                raise
        return view(request, row)
    try:
        return await run_in_threadpool(work)
    except PictureError as exc:
        raise picture_error(exc) from exc


@router.post("/assignments/{assignment_id}/ai-check", status_code=201)
def ask_for_check(assignment_id: int, request: Request, user: dict = Depends(learner)) -> dict:
    """The student asks for an AI check of their handed-in, not yet checked answer. It waits for the teacher."""
    store, here = request.app.state.store, reads.of(request)
    assignment = _my_assignment(request, user, assignment_id)
    klass = here.get_class(assignment["class_id"])
    if not klass or not klass["ai_enabled"]:
        raise HTTPException(409, "ה־AI כבוי בכיתה הזו")
    sub = store.get_submission(assignment_id, user["id"])
    if assignment["kind"] == "exercise_test" or sub is None or sub["state"] != "handed_in":
        raise HTTPException(409, "אפשר לבקש בדיקה רק להגשה שעוד לא נבדקה")
    if store.ai_requests(user_id=user["id"], assignment_id=assignment_id, kinds=["check"], states=OPEN):
        raise HTTPException(409, "כבר ביקשתם בדיקה להגשה הזו")
    _check_student_limits(request, user, False)
    row = store.create_ai_request("check", user["id"], klass["id"], assignment_id=assignment_id, snapshot=snapshot_of(request, assignment), created_at=clock.now())
    return view(request, row)


@router.post("/assignments/{assignment_id}/look-again", status_code=201)
def ask_to_look_again(assignment_id: int, request: Request, user: dict = Depends(learner)) -> dict:
    """The student disagrees with a check or a grade and asks the teacher to look again: one open request per answer, five per student."""
    store = request.app.state.store
    assignment = _my_assignment(request, user, assignment_id)
    sub = store.get_submission(assignment_id, user["id"])
    done_check = store.ai_requests(user_id=user["id"], assignment_id=assignment_id, kinds=["check"], states=["done"])
    if sub is None or not (sub["state"] in ("graded", "returned") or done_check):
        raise HTTPException(409, "אפשר לבקש בדיקה חוזרת רק אחרי בדיקה")
    mine = store.ai_requests(user_id=user["id"], kinds=["again"], states=["waiting"])
    if any(r["assignment_id"] == assignment_id for r in mine):
        raise HTTPException(409, "כבר ביקשתם מהמורה לבדוק שוב")
    if len(mine) >= MAX_LOOK_AGAIN:
        raise HTTPException(429, f"יש כבר {MAX_LOOK_AGAIN} בקשות לבדיקה חוזרת פתוחות")
    row = store.create_ai_request("again", user["id"], assignment["class_id"], assignment_id=assignment_id, created_at=clock.now())
    return view(request, row)


def close_look_again(store, assignment_id: int, user_id: str) -> None:
    """Saving a review closes the student's open requests to look again."""
    for r in store.ai_requests(user_id=user_id, assignment_id=assignment_id, kinds=["again"], states=["waiting"]):
        store.save_ai_request(r["id"], state="closed", done_at=clock.now())


@router.get("/ai/status")
def ai_status(request: Request, user: dict = Depends(learner)) -> dict:
    """Whether to show photo help: a student's classes have the AI on (a teacher or developer can always use it, with their allowance), and the
    student's latest requests with their state."""
    on = _is_staff(user) or any(c["ai_enabled"] for c in _student_classes(request, user))
    rows = request.app.state.store.ai_requests(user_id=user["id"], kinds=["photo"]) if on else []
    return {"on": on, "requests": [view(request, r) for r in reversed(rows) if r["state"] != "cancelled"][:5]}


@router.get("/ai/requests")
def my_requests(request: Request, user: dict = Depends(learner)) -> list[dict]:
    rows = request.app.state.store.ai_requests(user_id=user["id"])
    return [view(request, r, staff=_is_staff(user)) for r in reversed(rows)][:30]


def _readable(request: Request, user: dict, row: dict) -> bool:
    if row["user_id"] == user["id"]:
        return True
    if _developer(user):
        return True
    klass = request.app.state.store.get_class(row["class_id"]) if row["class_id"] else None
    return bool(klass and (klass["teacher_email"] or "").lower() == user["email"] and _is_staff(user))


def _mine_or_mine_to_handle(request: Request, user: dict, request_id: str) -> dict:
    row = request.app.state.store.get_ai_request(request_id)
    if row is None or not _readable(request, user, row):
        raise HTTPException(404, "הבקשה לא נמצאה")
    return row


@router.get("/ai/requests/{request_id}")
def one_request(request_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    row = _mine_or_mine_to_handle(request, user, request_id)
    emails = {m["user_id"]: m["email"] for m in request.app.state.store.members(row["class_id"]) if m["user_id"]} if row["class_id"] else {}
    return view(request, row, staff=row["user_id"] != user["id"] or _is_staff(user), emails=emails)


@router.post("/ai/requests/{request_id}/cancel")
def cancel(request_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    store = request.app.state.store
    row = store.get_ai_request(request_id)
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(404, "הבקשה לא נמצאה")
    if row["state"] != "waiting":
        raise HTTPException(409, "אפשר לבטל רק בקשה שעדיין מחכה")
    saved = store.save_ai_request(request_id, state="cancelled", done_at=clock.now())
    _delete_photo(request.app, row)
    return view(request, saved)


# ---- the teacher ----

def _teachable(request: Request, user: dict) -> list[dict]:
    store = request.app.state.store
    return store.classes() if _developer(user) else store.classes_taught(user["email"])


def _handle(request: Request, user: dict, request_id: str) -> dict:
    """A request the teacher may send or decline: one of their classes' students' (a developer: any)."""
    row = request.app.state.store.get_ai_request(request_id)
    if row is None or row["kind"] == "again" or row["class_id"] is None:
        raise HTTPException(404, "הבקשה לא נמצאה")
    _my_class(request, user, row["class_id"])
    return row


@router.get("/ai/queue")
def queue(request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    """The AI requests of the classes the teacher teaches (a developer: every class): waiting, being processed, failed and today's done ones."""
    store, today = request.app.state.store, clock.school_day()
    classes = _teachable(request, user)
    ids = [c["id"] for c in classes]
    rows = store.ai_requests(class_ids=ids, kinds=["photo", "check"], states=["waiting", "processing", "failed", "done"]) if ids else []
    emails = {m["user_id"]: m["email"] for c in classes for m in reads.of(request).members(c["id"]) if m["user_id"]}
    rows = [r for r in rows if r["state"] != "done" or (r["done_at"] and clock.school_day(r["done_at"]) == today)]
    items = [view(request, r, staff=True, emails=emails) for r in rows]
    own = None if _developer(user) else {"allowance": TEACHER_ALLOWANCE, "used": store.ai_allowance_used(f"teacher:{user['email']}", today)}
    return {"waiting": sum(1 for r in rows if r["state"] == "waiting"), "items": items, "own": own,
            "classes": [{"id": c["id"], "name": c["name"], "ai_enabled": c["ai_enabled"], "daily": c["ai_daily_checks"],
                         "used": store.ai_allowance_used(f"class:{c['id']}", today)} for c in classes]}


@router.post("/ai/requests/{request_id}/send")
def send_request(request_id: str, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    row = _handle(request, user, request_id)
    return view(request, send(request, user, row), staff=True)


class Decline(BaseModel):
    note: str = Field(default="", max_length=500)


@router.post("/ai/requests/{request_id}/decline")
def decline(request_id: str, body: Decline, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    row = _handle(request, user, request_id)
    if row["state"] not in ("waiting", "failed"):
        raise HTTPException(409, "הבקשה כבר טופלה")
    saved = request.app.state.store.save_ai_request(request_id, state="declined", teacher_note=body.note.strip(), done_at=clock.now())
    _delete_photo(request.app, row)
    return view(request, saved, staff=True)


class Batch(BaseModel):
    scope: Literal["photos", "assignment"]
    class_id: int | None = None
    assignment_id: int | None = None


@router.post("/ai/batch")
def batch(body: Batch, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    """Send every waiting request of one scope, oldest first (the single help photos of the teacher's classes, or one assignment's checks). When the
    budget is short it sends what is left and the rest stays waiting."""
    store = request.app.state.store
    if body.scope == "assignment":
        if body.assignment_id is None:
            raise HTTPException(422, "חסרה המשימה")
        assignment = store.get_assignment(body.assignment_id)
        if assignment is None:
            raise HTTPException(404, "המשימה לא נמצאה")
        _my_class(request, user, assignment["class_id"])
        rows = store.ai_requests(assignment_id=body.assignment_id, kinds=["check"], states=["waiting"])
    else:
        ids = [c["id"] for c in _teachable(request, user) if body.class_id in (None, c["id"])]
        rows = store.ai_requests(class_ids=ids, kinds=["photo"], states=["waiting"]) if ids else []
    sent, short = 0, False
    for row in rows:
        try:
            send(request, user, row)
            sent += 1
        except HTTPException as exc:
            if exc.status_code == 429:
                short = True
                break
            if exc.status_code == 409:                               # the class's AI was switched off, or it was handled already: leave it
                continue
    return {"sent": sent, "left": len(rows) - sent, "short": short,
            "message": ("המכסה היומית נגמרה. מה שנשאר ימשיך לחכות למחר." if short else "")}


@router.post("/submissions/{submission_id}/ai-check", status_code=201)
def teacher_asks_for_check(submission_id: int, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    """The teacher asks for an AI check of a handed-in answer and it is sent at once (it counts against the class's budget)."""
    store = request.app.state.store
    sub = store.get_submission_by_id(submission_id)
    assignment = store.get_assignment(sub["assignment_id"]) if sub else None
    if sub is None or assignment is None or assignment["removed_at"]:
        raise HTTPException(404, "ההגשה לא נמצאה")
    _my_class(request, user, assignment["class_id"])
    if store.ai_requests(user_id=sub["user_id"], assignment_id=assignment["id"], kinds=["check"], states=OPEN):
        raise HTTPException(409, "כבר ביקשו בדיקה להגשה הזו")
    row = store.create_ai_request("check", sub["user_id"], assignment["class_id"], assignment_id=assignment["id"],
                                  snapshot=snapshot_of(request, assignment), created_at=clock.now())
    try:
        row = send(request, user, row)
    except HTTPException:
        store.save_ai_request(row["id"], state="cancelled")
        raise
    return view(request, row, staff=True)


def latest_check(store, assignment_id: int, user_id: str) -> dict | None:
    """The newest AI check that finished for an answer (the teacher's review is kept next to it and never replaces it)."""
    done = store.ai_requests(user_id=user_id, assignment_id=assignment_id, kinds=["check"], states=["done"])
    return done[-1] if done else None
