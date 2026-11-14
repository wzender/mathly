"""Written answers: uploading pictures, reading them back (only through the server), photo requests to a phone, and push notifications."""
from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import clock, pictures, reads
from .access import allowed, learner
from .pictures import PictureError

router = APIRouter(prefix="/api")

MESSAGES = {
    "image_too_large": "התמונה גדולה מדי (עד 5MB)",
    "unsupported_image": "אפשר להעלות רק תמונות JPEG, PNG או WebP",
    "bad_image": "הקובץ לא נראה כמו תמונה תקינה",
    "not_a_pdf": "הקובץ אינו PDF",
    "bad_pdf": "לא הצלחנו לקרוא את ה־PDF",
    "pdf_too_large": "ה־PDF גדול מדי (עד 10MB)",
    "pdf_too_many_pages": "ב־PDF יש יותר מדי עמודים (עד 20)",
    "pdf_too_slow": "ה־PDF ארוך מדי לעיבוד",
    "picture_missing": "התמונה לא נמצאה",
    "answer_storage_unavailable": "האחסון של התמונות לא זמין כרגע. נסו שוב בעוד רגע.",
}


def picture_error(exc: PictureError) -> HTTPException:
    return HTTPException(exc.status, MESSAGES.get(exc.code, exc.code))


def _class_ids_of(request: Request, picture: dict) -> set[int]:
    """The classes whose assignments or submissions refer to a picture."""
    store = request.app.state.store
    refs = store.picture_refs(picture["id"])
    classes: set[int] = set()
    for assignment_id in refs["assignments"]:
        found = store.get_assignment(assignment_id)
        if found:
            classes.add(found["class_id"])
    for submission_id in refs["submissions"]:
        sub = store.get_submission_by_id(submission_id)
        found = store.get_assignment(sub["assignment_id"]) if sub else None
        if found:
            classes.add(found["class_id"])
    for rid in refs.get("ai_requests", []):
        asked = store.get_ai_request(rid)
        if asked and asked["class_id"]:
            classes.add(asked["class_id"])
    return classes


def can_read_picture(request: Request, user: dict, picture: dict) -> bool:
    """Who may read a picture: its uploader; a developer; the teacher of a class whose assignment or submission refers to it; and, for a page
    of an assignment, a student of that class. (A manager or an admin sees no learning data, so no pictures.)"""
    if picture["owner_id"] == user["id"] or allowed(user["roles"], "*"):
        return True
    store, here = request.app.state.store, reads.of(request)
    if picture["kind"] == "work":                                       # the board of an answer: the teachers of the student's classes
        from .boardwork import teaches_student
        return teaches_student(request, user, picture["owner_id"])
    classes = _class_ids_of(request, picture)
    if not classes:
        return False
    for class_id in classes:
        found = store.get_class(class_id)
        if found and (found["teacher_email"] or "").lower() == user["email"]:
            return True
    if picture["kind"] == "page":
        return any(c["id"] in classes for c in here.classes_of_student(user["email"]))
    return False


@router.post("/pictures", status_code=201)
async def upload_picture(request: Request, user: dict = Depends(learner)) -> dict:
    """A student's written answer as a picture (raw image bytes; the Content-Type says which kind). Nothing refers to it until it is handed in."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > pictures.MAX_IMAGE + 1024:
        raise picture_error(PictureError(413, "image_too_large"))
    data = await request.body()
    kind = request.headers.get("content-type", "")

    def work() -> dict:
        jpeg = pictures.clean_image(data, kind)
        return pictures.store_picture(request.app.state.store, request.app.state.pictures, user["id"], "answer", jpeg)
    try:
        row = await run_in_threadpool(work)
    except PictureError as exc:
        raise picture_error(exc) from exc
    return {"id": row["id"], "size": row["size"]}


@router.get("/pictures/{picture_id}")
def read_picture(picture_id: str, request: Request, user: dict = Depends(learner)) -> Response:
    """The bytes of a picture, if the caller may see it. Never a link into storage."""
    picture = request.app.state.store.get_picture(picture_id)
    if picture is None or not can_read_picture(request, user, picture):
        raise HTTPException(404, MESSAGES["picture_missing"])
    if picture["deleted_at"]:
        raise HTTPException(410, "התמונה נמחקה")
    try:
        data = request.app.state.pictures.get(picture["path"])
    except PictureError as exc:
        raise picture_error(exc) from exc
    return Response(data, media_type=picture["content_type"], headers={"Cache-Control": "private, max-age=3600"})


# ---- the photo request: a computer asks the student's phone for a photo of one answer ----

REQUEST_MINUTES = 10
REQUEST_MESSAGES = {"expired": "בקשת הצילום פגה. צרו בקשה חדשה ונסו שוב.", "superseded": "הבקשה הוחלפה בבקשה חדשה יותר.",
                    "received": "התמונה כבר התקבלה.", "failed": "ההעלאה נכשלה. צרו בקשה חדשה."}


class NewRequest(BaseModel):
    assignment_id: int
    device: str = Field(min_length=1, max_length=100)


def _new_code(request: Request) -> str:
    maker = getattr(request.app.state, "photo_code", None)
    return f"{(maker() if maker else secrets.randbelow(10000)):04d}"


def _settled(request: Request, row: dict) -> dict:
    """A request as it stands now: one that waited past its time is expired (decided when it is read, so no job runs)."""
    if row["state"] in ("waiting", "uploading") and clock.now() >= row["expires_at"]:
        return request.app.state.store.save_photo_request(row["id"], state="expired")
    return row


def _my_request(request: Request, user: dict, request_id: str) -> dict:
    row = request.app.state.store.get_photo_request(request_id)
    if row is None or row["user_id"] != user["id"]:
        raise HTTPException(404, "בקשת הצילום לא נמצאה")
    return _settled(request, row)


def request_view(row: dict) -> dict:
    return {"id": row["id"], "state": row["state"], "code": row["code"], "assignment_id": row["assignment_id"], "picture_id": row["picture_id"],
            "expires_at": row["expires_at"].isoformat()}


@router.post("/photo-requests", status_code=201)
def create_photo_request(body: NewRequest, request: Request, user: dict = Depends(learner)) -> dict:
    """The computer asks for a photo of an answer: a 4-digit code (the phone shows the same one), valid for ten minutes. An older waiting
    request for the same assignment is replaced."""
    from .assignments import _my_assignment
    row = _my_assignment(request, user, body.assignment_id)
    if row["kind"] == "exercise_test":
        raise HTTPException(422, "מבחן תרגול לא מגישים בתמונה")
    now = clock.now()
    made = request.app.state.store.create_photo_request(user["id"], body.assignment_id, body.device, _new_code(request), now, now + timedelta(minutes=REQUEST_MINUTES))
    notify = getattr(request.app.state, "notify_request", None)
    if notify:
        notify(request, user, made, row)
    return request_view(made)


@router.get("/photo-requests/open")
def open_photo_requests(request: Request, device: str = "", user: dict = Depends(learner)) -> list[dict]:
    """The phone's list: requests waiting for a picture, except the ones made by this very device (the computer that asked)."""
    store = request.app.state.store
    found = []
    for row in store.open_photo_requests(user["id"]):
        row = _settled(request, row)
        if row["state"] in ("waiting", "uploading") and row["device"] != device:
            assignment = store.get_assignment(row["assignment_id"])
            found.append({**request_view(row), "assignment": {"id": row["assignment_id"], "title": assignment["title"] if assignment else ""}})
    return found


@router.get("/photo-requests/{request_id}")
def read_photo_request(request_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    return request_view(_my_request(request, user, request_id))


@router.post("/photo-requests/{request_id}/start")
def start_photo_upload(request_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """The phone began: the computer shows "uploading"."""
    row = _my_request(request, user, request_id)
    if row["state"] not in ("waiting", "uploading"):
        raise HTTPException(409, REQUEST_MESSAGES.get(row["state"], "הבקשה לא פתוחה"))
    return request_view(request.app.state.store.save_photo_request(row["id"], state="uploading"))


@router.post("/photo-requests/{request_id}/picture")
async def photo_request_picture(request_id: str, request: Request, user: dict = Depends(learner)) -> dict:
    """The phone's photo (raw image bytes): cleaned and kept; the request becomes "received" with its picture, or "failed"."""
    row = _my_request(request, user, request_id)
    if row["state"] not in ("waiting", "uploading"):
        raise HTTPException(409, REQUEST_MESSAGES.get(row["state"], "הבקשה לא פתוחה"))
    store = request.app.state.store
    store.save_photo_request(row["id"], state="uploading")
    data, kind = await request.body(), request.headers.get("content-type", "")

    def work() -> dict:
        return pictures.store_picture(store, request.app.state.pictures, user["id"], "answer", pictures.clean_image(data, kind))
    try:
        pic = await run_in_threadpool(work)
    except PictureError as exc:
        store.save_photo_request(row["id"], state="failed")
        raise picture_error(exc) from exc
    return request_view(store.save_photo_request(row["id"], state="received", picture_id=pic["id"]))


# ---- push notifications ----

class Subscription(BaseModel):
    endpoint: str = Field(max_length=1000)
    keys: dict = Field(default_factory=dict)


class Unsubscribe(BaseModel):
    endpoint: str = Field(max_length=1000)


def _pusher(request: Request):
    return request.app.state.pusher


@router.get("/push/key")
def push_key(request: Request, user: dict = Depends(learner)) -> Response:
    """The server's public push key for the page to subscribe with; `enabled: false` (and no key) when notifications are off."""
    pusher = _pusher(request)
    body = {"enabled": bool(pusher and pusher.on), "key": pusher.public if pusher and pusher.on else ""}
    return Response(__import__("json").dumps(body), media_type="application/json", headers={"Cache-Control": "no-store"})


@router.post("/push/subscribe")
def push_subscribe(body: Subscription, request: Request, user: dict = Depends(learner)) -> dict:
    pusher = _pusher(request)
    if not pusher or not pusher.on:
        raise HTTPException(503, "התראות כבויות בשרת")
    try:
        pusher.subscribe(user["id"], body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, "זו לא הרשמה להתראות") from exc
    return {"ok": True}


@router.post("/push/unsubscribe")
def push_unsubscribe(body: Unsubscribe, request: Request, user: dict = Depends(learner)) -> dict:
    store = request.app.state.store
    mine = {s["endpoint"] for s in store.push_subscriptions_of(user["id"])}
    if body.endpoint in mine:
        store.delete_push_subscription(body.endpoint)
    return {"ok": True}


def notify_new_request(request: Request, user: dict, made: dict, assignment: dict) -> None:
    """A new photo request: the student's phones are told, with the request's time left as the notification's life. Never raises."""
    from . import push
    pusher = _pusher(request)
    try:
        if pusher and pusher.on:
            pusher.notify(user["id"], push.request_payload(made, assignment), push.seconds_left(made, clock.now()))
    except Exception:                                                 # the phone still finds the request when the app opens
        import logging
        logging.getLogger("mathly.push").exception("photo request not pushed")
