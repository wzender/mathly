"""A worksheet becomes a lesson (add-subjects-and-worksheets, PRD WKS). A manager or a developer starts an upload for a new or existing
subject, sends the worksheet's file(s), and asks the AI for a draft; the draft is then edited and published (lessons.py, subjects.py).

The worksheet is one PDF (up to 20 pages), 1 to 10 photos, or one Word document, up to 15 MB in all. Its files are kept in the
private bucket m2-worksheets (`app.state.worksheet_files`), read and written only by the server: the original PDF or Word file,
a picture per page shown beside the editor, and a Word document's text. Drafting runs in a small background pool, so the upload
returns at once and the editor polls the lesson's status: drafting, then ready (with the draft) or failed (with the reason in
words, ai.FAILURES). A lesson left drafting by a restart is marked failed ("interrupted") and can be retried without a new upload.
The AI gets only the worksheet and the subject's name, never a person's or a class's name.
"""
from __future__ import annotations

import io
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from . import ai, clock, content, pictures
from .access import need
from .lessons import assign_ids
from .pictures import PictureError
from .store import SubjectExists
from .written import MESSAGES

log = logging.getLogger("mathly2.worksheets")
router = APIRouter(prefix="/api/worksheets")
POOL = ThreadPoolExecutor(max_workers=2, thread_name_prefix="worksheet")

MAX_BYTES = 15_000_000           # the whole worksheet
MAX_PHOTOS = 10
DAILY_UPLOADS = 20               # worksheets a person may start a day (each draft is a paid AI call)
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
KINDS = {"application/pdf": "pdf", DOCX: "docx", **{t: "photo" for t in pictures.ALLOWED}}
SOURCES = ("pdf", "docx", "photo")
REFUSED = "אפשר להעלות PDF אחד (עד 20 עמודים), עד 10 תמונות, או מסמך Word אחד, עד 15MB בסך הכול"


class StartBody(BaseModel):
    subject_id: str | None = Field(default=None, max_length=40)
    new_subject: str | None = Field(default=None, max_length=200)      # a new subject's name (with its icon)
    icon: str | None = Field(default=None, max_length=8)


def _files(request: Request):
    return request.app.state.worksheet_files


def _lesson(request: Request, lesson_id: int) -> dict:
    row = request.app.state.store.get_lesson(lesson_id)
    if row is None or row["source"] != "worksheet":
        raise HTTPException(404, "דף העבודה לא נמצא")
    return row


def failure_words(failure: str | None) -> dict | None:
    """The stored failure ("reason" or "reason: detail") as what happened and what to do."""
    if not failure:
        return None
    reason, _, detail = failure.partition(": ")
    what, todo = ai.FAILURES.get(reason, ai.FAILURES["provider_error"])
    return {"reason": reason, "what": what, "todo": todo, "note": detail if reason == "unreadable" else ""}


def view(row: dict) -> dict:
    """A worksheet lesson as the editor reads it: its state, the pages to show beside the draft, and the draft."""
    pages = [i for i, f in enumerate(row["files"]) if f["kind"] == "page"]
    text = next((f for f in row["files"] if f["kind"] == "text"), None)
    sources = [f["kind"] for f in row["files"] if f["kind"] in SOURCES]
    return {"id": row["id"], "subject_id": row["subject_id"], "status": row["status"], "failure": failure_words(row.get("failure")),
            "published": row["published"] is not None, "pages": pages, "has_text": text is not None, "sources": sources,
            "draft": row["draft"] if row["status"] == "ready" and row["draft"] else None}


def _today_uploads(store, email: str) -> int:
    start = clock.now() - timedelta(days=1)
    return sum(1 for l in store.lessons_of() if l["source"] == "worksheet" and l["created_by"] == email and l["created_at"] and l["created_at"] >= start)


@router.post("", status_code=201)
def start(body: StartBody, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    """A new worksheet for an existing subject, or for a new subject named here. Files follow; then the draft is asked for."""
    from .subjects import ICONS, _name
    store = request.app.state.store
    if _today_uploads(store, user["email"]) >= DAILY_UPLOADS:
        raise HTTPException(429, f"אפשר להעלות עד {DAILY_UPLOADS} דפי עבודה ביום. נסו שוב מחר.")
    if body.new_subject is not None:
        icon = body.icon if body.icon in ICONS else ICONS[0]
        try:
            subject = store.create_subject(f"s{uuid.uuid4().hex[:8]}", _name(body.new_subject), user["email"], icon=icon)
        except SubjectExists:
            raise HTTPException(409, "כבר יש מקצוע בשם הזה") from None
        content.rebuild(request.app)
    else:
        subject = next((s for s in store.subjects() if s["id"] == body.subject_id), None)
        if subject is None:
            raise HTTPException(404, "המקצוע לא נמצא")
    row = store.create_lesson(subject["id"], user["email"], {}, source="worksheet", status="ready")
    return view(row)


def _docx(data: bytes) -> tuple[str, list[bytes]]:
    """A Word document's text (paragraphs and table cells, in order) and its pictures as cleaned JPEGs."""
    import docx
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:                                  # not a .docx, or a broken one
        raise PictureError(400, "bad_docx") from exc
    lines = [p.text for p in document.paragraphs if p.text.strip()]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    images = []
    for rel in document.part.rels.values():
        if "image" in rel.reltype:
            blob = rel.target_part.blob
            kind = rel.target_part.content_type
            if kind in pictures.ALLOWED and len(images) < MAX_PHOTOS:
                try:
                    images.append(pictures.clean_image(blob, kind))
                except PictureError:
                    continue                                  # a picture we cannot read is left out; the text still goes
    if not lines and not images:
        raise PictureError(400, "empty_docx")
    return "\n".join(lines), images


MESSAGES.update({"bad_docx": "לא הצלחנו לקרוא את מסמך ה־Word", "empty_docx": "במסמך ה־Word אין טקסט או תמונות",
                 "worksheet_too_large": "דף העבודה גדול מדי (עד 15MB בסך הכול)"})


@router.post("/{lesson_id}/files", status_code=201)
async def add_file(lesson_id: int, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    """One file of the worksheet, sent as the request body with its content type. A PDF or a Word document is the whole worksheet;
    photos may come one by one, up to ten."""
    row = _lesson(request, lesson_id)
    if row["status"] == "drafting":
        raise HTTPException(409, "הטיוטה בהכנה. אפשר להוסיף קבצים אחרי שהיא תסתיים")
    kind_header = request.headers.get("content-type", "").split(";")[0].strip().lower()
    kind = KINDS.get(kind_header)
    if kind is None:
        raise HTTPException(415, REFUSED)
    data = await request.body()
    have = [f["kind"] for f in row["files"] if f["kind"] in SOURCES]
    size = sum(f.get("size", 0) for f in row["files"] if f["kind"] in SOURCES) + len(data)
    if (have and (kind != "photo" or have[0] != "photo")) or have.count("photo") >= MAX_PHOTOS:
        raise HTTPException(422, REFUSED)
    if size > MAX_BYTES:
        raise HTTPException(413, MESSAGES["worksheet_too_large"])

    def work() -> list[dict]:
        store_files, base, n = _files(request), f"lessons/{lesson_id}", len(row["files"])
        added = []
        if kind == "pdf":
            pages = pictures.render_pdf(data, MAX_BYTES)
            store_files.put(f"{base}/source.pdf", data, "application/pdf")
            added.append({"kind": "pdf", "path": f"{base}/source.pdf", "size": len(data)})
        elif kind == "docx":
            text, pages = _docx(data)
            store_files.put(f"{base}/source.docx", data, DOCX)
            store_files.put(f"{base}/text.txt", text.encode("utf-8"), "text/plain")
            added += [{"kind": "docx", "path": f"{base}/source.docx", "size": len(data)}, {"kind": "text", "path": f"{base}/text.txt"}]
        else:
            pages = [pictures.clean_image(data, kind_header)]
            added.append({"kind": "photo", "path": f"{base}/page-{n}.jpg", "size": len(data)})
        for i, page in enumerate(pages):
            path = f"{base}/page-{n + i}.jpg"
            store_files.put(path, page, "image/jpeg")
            added.append({"kind": "page", "path": path})
        return added
    try:
        added = await run_in_threadpool(work)
    except PictureError as exc:
        raise HTTPException(exc.status, MESSAGES.get(exc.code, exc.code)) from exc
    return view(request.app.state.store.save_lesson(lesson_id, files=row["files"] + added))


@router.get("/{lesson_id}")
def read(lesson_id: int, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    return view(_lesson(request, lesson_id))


@router.get("/{lesson_id}/pages/{index}")
def page(lesson_id: int, index: int, request: Request, user: dict = Depends(need("content.manage"))) -> Response:
    row = _lesson(request, lesson_id)
    if not 0 <= index < len(row["files"]) or row["files"][index]["kind"] != "page":
        raise HTTPException(404, "העמוד לא נמצא")
    return Response(_files(request).get(row["files"][index]["path"]), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.get("/{lesson_id}/text")
def text(lesson_id: int, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    row = _lesson(request, lesson_id)
    found = next((f for f in row["files"] if f["kind"] == "text"), None)
    if found is None:
        raise HTTPException(404, "אין טקסט לדף הזה")
    return {"text": _files(request).get(found["path"]).decode("utf-8")}


def parts_of(app, row: dict) -> list[dict]:
    """The worksheet as the AI gets it: the PDF itself, or the photos, or a Word document's text and pictures."""
    files, kinds = app.state.worksheet_files, [f["kind"] for f in row["files"]]
    if "pdf" in kinds:
        return [{"kind": "pdf", "data": files.get(next(f["path"] for f in row["files"] if f["kind"] == "pdf"))}]
    parts = []
    if "text" in kinds:
        parts.append({"kind": "text", "text": files.get(next(f["path"] for f in row["files"] if f["kind"] == "text")).decode("utf-8")})
    parts += [{"kind": "image", "media_type": "image/jpeg", "data": files.get(f["path"])} for f in row["files"] if f["kind"] == "page"]
    return parts


def run(app, lesson_id: int, user_id: str | None) -> None:
    """Ask the AI for the draft and keep it, or keep why it failed. Never raises: the editor reads the outcome from the lesson."""
    store = app.state.store
    try:
        row = store.get_lesson(lesson_id)
        subject = next((s["name"] for s in store.subjects() if s["id"] == row["subject_id"]), "")
        result = app.state.ai.draft_lesson(parts_of(app, row), subject)
        draft = assign_ids(result["lesson"], lesson_id)
        store.save_lesson(lesson_id, draft=draft, status="ready", failure=None)
    except ai.AIFailure as exc:
        log.warning("worksheet %s: drafting failed: %s (%s)", lesson_id, exc.reason, exc.detail)
        store.save_lesson(lesson_id, status="failed", failure=exc.reason + (f": {exc.detail}" if exc.reason == "unreadable" and exc.detail else ""))
        return
    except Exception as exc:                                  # anything else: the lesson must not stay "drafting"
        log.exception("worksheet %s: drafting broke", lesson_id)
        store.save_lesson(lesson_id, status="failed", failure="provider_error")
        return
    try:
        if result.get("usage"):
            store.add_ai_usage(ai.usage_row(result["usage"], "worksheet", None, user_id))
    except Exception as exc:                                  # recording the cost never fails the draft
        log.warning("worksheet %s: usage not recorded: %s", lesson_id, type(exc).__name__)


@router.post("/{lesson_id}/draft")
def draft(lesson_id: int, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    """Ask the AI for the draft (again, after a failure): no new upload is needed. A published lesson is edited, not drafted again."""
    row = _lesson(request, lesson_id)
    if row["status"] == "drafting":
        return view(row)
    if row["published"] is not None:
        raise HTTPException(409, "השיעור כבר פורסם. עורכים אותו ישירות")
    if not any(f["kind"] in SOURCES for f in row["files"]):
        raise HTTPException(422, "קודם מעלים את דף העבודה")
    saved = request.app.state.store.save_lesson(lesson_id, status="drafting", failure=None)
    request.app.state.run_worksheet(request.app, lesson_id, user["id"])
    return view(saved)


def submit(app, lesson_id: int, user_id: str | None) -> None:
    POOL.submit(run, app, lesson_id, user_id)


def recover_after_restart(store) -> int:
    """Lessons left drafting when the server stopped: failed ("interrupted"), so the uploader can try again."""
    try:
        stuck = [l for l in store.lessons_of() if l["status"] == "drafting"]
        for lesson in stuck:
            store.save_lesson(lesson["id"], status="failed", failure="interrupted")
        return len(stuck)
    except Exception as exc:                                  # the lessons table may not be migrated yet
        log.warning("could not check worksheets after a restart: %s", exc)
        return 0
