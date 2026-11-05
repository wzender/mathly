"""Worksheets: a PDF or photos a class teacher attaches to an assignment, and the students' photographed solutions.

A worksheet (Supabase `math_worksheets`) belongs to one class. The teacher uploads it first, then saves an assignment
with a `{"kind": "worksheet", "id"}` item (app/assignments.py). A worksheet that no assignment uses is deleted after a
day by the hourly cleanup (app/answer_cleanup.py), and one dropped from an assignment, or whose assignment is deleted,
goes at once, with its submissions.

A PDF is rendered to page images here, so every phone shows it the same way; the PDF itself is kept to download.
Photos, the teacher's and the students', go through `clean_image` (re-encoded, metadata dropped).

A student hands in 1 to 10 photos (`math_worksheet_submissions`, one per student and worksheet) and may replace them
until the teacher checks. The teacher's check is a time, an optional score (0-100) and an optional comment.

Files live in the private `mathly-worksheets` bucket. Only the server reads or writes rows and files, with the service
key; the browser never sees a storage path.
"""
from __future__ import annotations

import io
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from .access import has_permission
from . import ai_usage
from .answer_routes import grading_key, open_ended_locked
from .answer_scans import MAX_IMAGE, ScanError, clean_image
from .auth import AuthUnavailable, ClassConflict
from .homework_grading import HomeworkGrader
from .math_photo import PhotoUnavailable
from .teacher_ai import LimitReached, MESSAGE as TEACHER_AI_MESSAGE

log = logging.getLogger("mathly.worksheets")
MIGRATION = "supabase/migrations/20261105090000_math_worksheets.sql"
BUCKET = "mathly-worksheets"
MAX_PDF = 10_000_000
MAX_PAGES = 10
MAX_TITLE = 80
MAX_COMMENT = 1000
PAGE_WIDTH = 1600           # a rendered PDF page, in pixels
RENDER_BUDGET = 30.0        # seconds for all the pages of one PDF
UNUSED_AGE = timedelta(hours=24)
W_FIELDS = "id,class_id,title,source,pages,original_key,page_keys,byte_size,created_by_email,created_at"
S_FIELDS = "id,worksheet_id,student_id,student_email,page_keys,submitted_at,checked_at,score,comment,checked_by_email"


class WorksheetsUnavailable(RuntimeError):
    pass


class Worksheets:
    """Rows through the service key (auth._admin), files in the private bucket."""

    def __init__(self, auth):
        self.auth = auth
        self._warned = False

    @property
    def configured(self) -> bool:
        return bool(self.auth is not None and getattr(self.auth, "secret", None))

    # ---- rows
    def _rest(self, path: str, method: str = "GET", body=None, prefer: str = "return=representation"):
        if not self.configured:
            raise WorksheetsUnavailable("worksheets_unavailable")
        try:
            return self.auth._admin(path, method, body, prefer) or []
        except ClassConflict as exc:
            raise WorksheetsUnavailable("worksheets_unavailable") from exc
        except AuthUnavailable as exc:
            if "answered 404" in str(exc) and not self._warned:
                log.warning("the worksheet tables are missing; apply %s", MIGRATION)
                self._warned = True
            raise WorksheetsUnavailable("worksheets_unavailable") from exc

    def add(self, row: dict) -> dict:
        return self._rest(f"/rest/v1/math_worksheets?select={W_FIELDS}", "POST", row)[0]

    def get(self, worksheet_id: str) -> dict | None:
        rows = self._rest(f"/rest/v1/math_worksheets?select={W_FIELDS}&id=eq.{worksheet_id}")
        return rows[0] if rows else None

    def of_class(self, class_id: int) -> list[dict]:
        return self._rest(f"/rest/v1/math_worksheets?select={W_FIELDS}&class_id=eq.{int(class_id)}&order=created_at.asc")

    def by_ids(self, ids) -> list[dict]:
        ids = sorted(set(ids))
        if not ids:
            return []
        return self._rest(f"/rest/v1/math_worksheets?select={W_FIELDS}&id=in.({','.join(ids)})")

    def older_than(self, cutoff: datetime) -> list[dict]:
        at = urllib.parse.quote(cutoff.astimezone(timezone.utc).isoformat())
        return self._rest(f"/rest/v1/math_worksheets?select={W_FIELDS}&created_at=lt.{at}")

    def remove(self, worksheet_id: str) -> None:
        self._rest(f"/rest/v1/math_worksheets?id=eq.{worksheet_id}", "DELETE")

    def submissions(self, worksheet_ids, student_id: str | None = None) -> list[dict]:
        ids = sorted(set(worksheet_ids))
        if not ids:
            return []
        who = f"&student_id=eq.{student_id}" if student_id else ""
        return self._rest(f"/rest/v1/math_worksheet_submissions?select={S_FIELDS}&worksheet_id=in.({','.join(ids)}){who}")

    def submission(self, submission_id: str) -> dict | None:
        rows = self._rest(f"/rest/v1/math_worksheet_submissions?select={S_FIELDS}&id=eq.{submission_id}")
        return rows[0] if rows else None

    def save_submission(self, row: dict) -> dict:
        """Creates the student's submission of a worksheet, or replaces it (one per student and worksheet)."""
        return self._rest(f"/rest/v1/math_worksheet_submissions?on_conflict=worksheet_id,student_id&select={S_FIELDS}",
                          "POST", row, "return=representation,resolution=merge-duplicates")[0]

    def check(self, submission_id: str, fields: dict) -> dict | None:
        rows = self._rest(f"/rest/v1/math_worksheet_submissions?id=eq.{submission_id}&select={S_FIELDS}", "PATCH", fields)
        return rows[0] if rows else None

    # ---- files
    def _storage(self, path: str, method: str = "GET", data: bytes | None = None, content_type: str | None = None) -> bytes:
        if not self.configured:
            raise WorksheetsUnavailable("worksheets_unavailable")
        headers = {"Authorization": "Bearer " + self.auth.secret, "apikey": self.auth.secret, "User-Agent": "mathly/1.0"}
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(self.auth.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            # never pass keys or storage paths on to the browser
            log.warning("worksheet storage failed: %s", getattr(exc, "code", type(exc).__name__))
            raise WorksheetsUnavailable("worksheets_unavailable") from exc

    def put(self, key: str, data: bytes, content_type: str = "image/jpeg") -> None:
        self._storage(f"/storage/v1/object/{BUCKET}/{urllib.parse.quote(key, safe='/')}", "POST", data, content_type)

    def read(self, key: str) -> bytes:
        return self._storage(f"/storage/v1/object/authenticated/{BUCKET}/{urllib.parse.quote(key, safe='/')}")

    def delete(self, keys: list[str]) -> None:
        keys = [k for k in keys if k]
        if keys:
            self._storage(f"/storage/v1/object/{BUCKET}", "DELETE", json.dumps({"prefixes": keys}).encode(), "application/json")


# ---- files in
def render_pdf(data: bytes) -> list[bytes]:
    """The pages of a PDF as JPEGs; HTTPException 400/413 when it is not one we take."""
    if len(data) > MAX_PDF:
        raise HTTPException(413, "pdf_too_large")
    if not data.startswith(b"%PDF-"):
        raise HTTPException(415, "not_a_pdf")
    import pypdfium2 as pdfium
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError as exc:
        raise HTTPException(400, "unreadable_pdf") from exc
    try:
        if len(doc) < 1:
            raise HTTPException(400, "unreadable_pdf")
        if len(doc) > MAX_PAGES:
            raise HTTPException(400, "too_many_pages")
        started, pages = time.monotonic(), []
        for page in doc:
            if time.monotonic() - started > RENDER_BUDGET:
                raise HTTPException(400, "pdf_too_slow")
            width, height = page.get_size()
            if width <= 0 or height <= 0:
                raise HTTPException(400, "unreadable_pdf")
            scale = min(PAGE_WIDTH / width, 2400 / height)   # at most 1600 wide and 2400 high
            image = page.render(scale=scale).to_pil().convert("RGB")
            image.thumbnail((PAGE_WIDTH, 2400))   # rendering rounds up a pixel
            out = io.BytesIO()
            image.save(out, "JPEG", quality=82, optimize=True)
            pages.append(out.getvalue())
        return pages
    except pdfium.PdfiumError as exc:
        raise HTTPException(400, "unreadable_pdf") from exc
    finally:
        doc.close()


async def read_upload(upload: UploadFile, limit: int) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, "file_too_large")
    return data


async def clean_photos(files: list[UploadFile]) -> list[bytes]:
    if not 1 <= len(files) <= MAX_PAGES:
        raise HTTPException(400, "too_many_pages" if files else "no_files")
    out = []
    for upload in files:
        data = await read_upload(upload, MAX_IMAGE)
        try:
            out.append(await run_in_threadpool(clean_image, data, upload.content_type or ""))
        except ScanError as exc:
            raise HTTPException(exc.status, exc.code) from exc
    return out


# ---- what the browser sees
def worksheet_public(row: dict) -> dict:
    return {k: row.get(k) for k in ("id", "class_id", "title", "source", "pages", "created_at")}


def submission_public(row: dict) -> dict:
    """A submission without its storage paths (the student's and the teacher's view)."""
    return {"id": row.get("id"), "worksheet_id": row.get("worksheet_id"), "pages": len(row.get("page_keys") or []),
            "submitted_at": row.get("submitted_at"), "checked_at": row.get("checked_at"), "score": row.get("score"),
            "comment": row.get("comment") or ""}


def worksheet_ids(items) -> list[str]:
    return [i["id"] for i in items or [] if isinstance(i, dict) and i.get("kind") == "worksheet" and i.get("id")]


def uuid_or_404(value: str, what: str = "worksheet") -> str:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError as exc:
        raise HTTPException(404, f"{what} not found") from exc


def drop(store: Worksheets, rows: list[dict]) -> None:
    """Deletes worksheets with their submissions (cascade) and every file of both."""
    for row in rows:
        keys = list(row.get("page_keys") or []) + [row.get("original_key")]
        try:
            keys += [k for s in store.submissions([row["id"]]) for k in s.get("page_keys") or []]
        except WorksheetsUnavailable:
            log.warning("a deleted worksheet's submission images may stay in storage")
        store.remove(row["id"])
        try:
            store.delete(keys)
        except WorksheetsUnavailable:
            log.warning("a deleted worksheet's files stayed in storage")


def drop_ids(store: Worksheets, ids) -> int:
    """Deletes these worksheets (see drop); the number deleted."""
    rows = store.by_ids(ids)
    drop(store, rows)
    return len(rows)


def cleanup_unused(store: Worksheets, assignments, now: datetime | None = None) -> int:
    """Deletes worksheets older than a day that no assignment of their class uses; the number deleted."""
    now = now or datetime.now(timezone.utc)
    old = store.older_than(now - UNUSED_AGE)
    if not old:
        return 0
    classes = sorted({r["class_id"] for r in old})
    used = {wid for r in assignments.for_classes(classes) for wid in worksheet_ids(r.get("items"))}
    unused = [r for r in old if r["id"] not in used]
    drop(store, unused)
    return len(unused)


def install_worksheet_routes(app, signed_in):
    if not hasattr(app.state, "worksheets"):
        app.state.worksheets = Worksheets(app.state.auth)

    def store() -> Worksheets:
        return app.state.worksheets

    async def call(fn, *args):
        try:
            return await run_in_threadpool(fn, *args)
        except WorksheetsUnavailable as exc:
            raise HTTPException(503, "worksheets_unavailable") from exc

    def reply(value, status=200):
        return JSONResponse(value, status_code=status, headers={"Cache-Control": "no-store"})

    def image(data: bytes, media_type: str = "image/jpeg", filename: str | None = None):
        headers = {"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"}
        if filename:
            headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{urllib.parse.quote(filename)}"
        return Response(data, media_type=media_type, headers=headers)

    def record(user, kind, label):
        actions = getattr(app.state, "actions", None)
        if actions is not None:
            actions.record(user, kind, label)

    def classes() -> list[dict]:
        try:
            return app.state.auth.classes()
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    def need_user(user):
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        return user

    def teaches(user, row) -> bool:
        return str(user.get("email", "")).lower() in row.get("teachers", ()) or has_permission(user, "management.access")

    def class_row(class_id: int, user: dict) -> dict:
        """The class, if this account is its teacher or a manager."""
        need_user(user)
        row = next((r for r in classes() if r.get("id") == class_id), None)
        if row is None:
            raise HTTPException(404, "class not found")
        if not teaches(user, row):
            raise HTTPException(403, "only the class's teacher can do this")
        return row

    async def worksheet_of(class_id: int, wid: str) -> dict:
        found = await call(store().get, uuid_or_404(wid))
        if not found or found.get("class_id") != class_id:
            raise HTTPException(404, "worksheet not found")
        return found

    async def readable(user: dict, wid: str) -> tuple[dict, dict]:
        """The worksheet and its class, when the account is in that class, teaches it, or is a manager; else 404."""
        need_user(user)
        found = await call(store().get, uuid_or_404(wid))
        row = next((r for r in classes() if found and r.get("id") == found.get("class_id")), None)
        email = str(user.get("email", "")).lower()
        if not found or row is None or not (email in row.get("emails", ()) or teaches(user, row)):
            raise HTTPException(404, "worksheet not found")   # of another class: as if it did not exist
        return found, row

    def page_index(n: int, count: int) -> int:
        if not 1 <= n <= count:
            raise HTTPException(404, "page not found")
        return n - 1

    # ---- the class teacher
    @app.post("/api/classes/{class_id}/worksheets")
    async def add_worksheet(class_id: int, title: str = Form(""), files: list[UploadFile] = File(...),
                            user=Depends(signed_in)):
        row = class_row(class_id, user)
        if not store().configured:
            raise HTTPException(503, "worksheets_unavailable")
        title = " ".join(title.split())
        if not title or len(title) > MAX_TITLE:
            raise HTTPException(400, f"the title is required (up to {MAX_TITLE} characters)")
        pdfs = [f for f in files if (f.content_type or "") == "application/pdf" or (f.filename or "").lower().endswith(".pdf")]
        original = None
        if pdfs:
            if len(files) != 1:
                raise HTTPException(400, "one_pdf_or_photos")
            original = await read_upload(files[0], MAX_PDF)
            pages = await run_in_threadpool(render_pdf, original)
        else:
            pages = await clean_photos(files)
        wid = str(uuid.uuid4())
        keys = [f"w/{wid}/{n + 1}.jpg" for n in range(len(pages))]
        original_key = f"w/{wid}/original.pdf" if original else None
        written = []
        try:
            for key, data in zip(keys, pages):
                await call(store().put, key, data)
                written.append(key)
            if original_key:
                await call(store().put, original_key, original, "application/pdf")
                written.append(original_key)
            saved = await call(store().add, {
                "id": wid, "class_id": class_id, "title": title, "source": "pdf" if original else "images",
                "pages": len(pages), "original_key": original_key, "page_keys": keys,
                "byte_size": sum(map(len, pages)) + len(original or b""),
                "created_by_email": str(user.get("email", "")).lower()})
        except HTTPException:
            try:
                await run_in_threadpool(store().delete, written)
            except WorksheetsUnavailable:
                pass   # files without a row are never shown
            raise
        record(user, "worksheet_added", f"{row.get('name', '')}: {title}")
        return reply(worksheet_public(saved), 201)

    @app.delete("/api/classes/{class_id}/worksheets/{wid}")
    async def delete_worksheet(class_id: int, wid: str, user=Depends(signed_in)):
        """An upload the teacher took back before saving: only while no assignment uses it."""
        class_row(class_id, user)
        found = await worksheet_of(class_id, wid)
        assignments = getattr(app.state, "assignments", None)
        try:
            used = {w for r in assignments.for_classes([class_id]) for w in worksheet_ids(r.get("items"))} if assignments else set()
        except Exception as exc:   # AssignmentsUnavailable: cannot tell it is unused
            raise HTTPException(503, "assignments_unavailable") from exc
        if found["id"] in used:
            raise HTTPException(409, "worksheet_in_use")
        await call(drop, store(), [found])
        return reply({"ok": True})

    @app.get("/api/classes/{class_id}/worksheets/{wid}/submissions/{sid}/pages/{n}")
    async def submission_page(class_id: int, wid: str, sid: str, n: int, user=Depends(signed_in)):
        class_row(class_id, user)
        found = await worksheet_of(class_id, wid)
        sub = await call(store().submission, uuid_or_404(sid, "submission"))
        if not sub or sub.get("worksheet_id") != found["id"]:
            raise HTTPException(404, "submission not found")
        keys = sub.get("page_keys") or []
        return image(await call(store().read, keys[page_index(n, len(keys))]))

    @app.put("/api/classes/{class_id}/worksheets/{wid}/submissions/{sid}")
    async def check_submission(class_id: int, wid: str, sid: str, body: dict, user=Depends(signed_in)):
        row = class_row(class_id, user)
        found = await worksheet_of(class_id, wid)
        score, comment = body.get("score"), body.get("comment", "")
        if score is not None and (type(score) is not int or not 0 <= score <= 100):
            raise HTTPException(400, "the score is a whole number from 0 to 100")
        if not isinstance(comment, str) or len(comment.strip()) > MAX_COMMENT:
            raise HTTPException(400, f"the comment is up to {MAX_COMMENT} characters")
        sub = await call(store().submission, uuid_or_404(sid, "submission"))
        if not sub or sub.get("worksheet_id") != found["id"]:
            raise HTTPException(404, "submission not found")
        saved = await call(store().check, sub["id"], {
            "score": score, "comment": comment.strip(), "checked_by_email": str(user.get("email", "")).lower(),
            "checked_at": sub.get("checked_at") or datetime.now(timezone.utc).isoformat()})
        if not saved:
            raise HTTPException(404, "submission not found")
        record(user, "worksheet_checked", f"{row.get('name', '')}: {found['title']}")
        return reply(submission_public(saved))

    @app.post("/api/classes/{class_id}/worksheets/{wid}/submissions/{sid}/ai-check")
    async def ai_check(class_id: int, wid: str, sid: str, user=Depends(signed_in)):
        """The AI's check of a submission, as a suggestion (score and comment) for the teacher; nothing is saved here.
        One of the teacher's daily AI requests (app/teacher_ai.py); given back when the AI could not answer."""
        row = class_row(class_id, user)
        found = await worksheet_of(class_id, wid)
        sub = await call(store().submission, uuid_or_404(sid, "submission"))
        if not sub or sub.get("worksheet_id") != found["id"]:
            raise HTTPException(404, "submission not found")
        if open_ended_locked():
            raise HTTPException(403, "open_ended_locked")
        key = grading_key()
        grader = getattr(app.state, "homework_grader", None)
        if not key and grader is None:
            raise HTTPException(503, "grading_unavailable")
        try:
            quota = app.state.teacher_ai.take(user)
        except LimitReached as exc:
            raise HTTPException(429, "teacher_ai_limit") from exc
        try:
            sheet = [await call(store().read, k) for k in found.get("page_keys") or []]
            solution = [await call(store().read, k) for k in sub.get("page_keys") or []]
            grader = grader or HomeworkGrader(key)
            result = await run_in_threadpool(grader.grade, found["title"], sheet, solution)
        except PhotoUnavailable as exc:
            app.state.teacher_ai.give_back(quota)
            raise HTTPException(503, f"ai_check_failed|{exc.reason or 'provider_error'}") from exc
        except Exception:
            app.state.teacher_ai.give_back(quota)
            raise
        ai_usage.record(app.state.auth, user.get("id"), "grading", result.pop("usage", None))
        if not result["readable"]:
            app.state.teacher_ai.give_back(quota)   # a photo the AI could not read is not one of the 3
        record(user, "worksheet_ai_checked", f"{row.get('name', '')}: {found['title']}")
        return reply({"score": result["score"], "comment": result["comment"], "readable": result["readable"],
                      "left": app.state.teacher_ai.left(user)})

    # ---- the class: the worksheet itself
    @app.get("/api/math/worksheets/{wid}/pages/{n}")
    async def worksheet_page(wid: str, n: int, user=Depends(signed_in)):
        found, _ = await readable(user, wid)
        keys = found.get("page_keys") or []
        return image(await call(store().read, keys[page_index(n, len(keys))]))

    @app.get("/api/math/worksheets/{wid}/original")
    async def worksheet_original(wid: str, user=Depends(signed_in)):
        found, _ = await readable(user, wid)
        if not found.get("original_key"):
            raise HTTPException(404, "this worksheet has no PDF")
        return image(await call(store().read, found["original_key"]), "application/pdf", f"{found['title']}.pdf")

    # ---- the student: their own submission
    async def member_worksheet(user: dict, wid: str) -> tuple[dict, dict]:
        """A worksheet of an assignment of one of the student's classes; else 404."""
        found, row = await readable(user, wid)
        if str(user.get("email", "")).lower() not in row.get("emails", ()):
            raise HTTPException(404, "worksheet not found")
        assignments = getattr(app.state, "assignments", None)
        try:
            used = {w for r in assignments.for_classes([row["id"]]) for w in worksheet_ids(r.get("items"))} if assignments else set()
        except Exception as exc:
            raise HTTPException(503, "assignments_unavailable") from exc
        if found["id"] not in used:
            raise HTTPException(404, "worksheet not found")
        return found, row

    app.state.member_worksheet = member_worksheet   # the answer routes' worksheet photos (app/answer_routes.py)

    async def own_submission(user: dict, wid: str) -> dict | None:
        rows = await call(store().submissions, [wid], user["id"])
        return rows[0] if rows else None

    @app.put("/api/math/worksheets/{wid}/submission")
    async def hand_in(wid: str, files: list[UploadFile] = File(...), user=Depends(signed_in)):
        found, row = await member_worksheet(user, wid)
        old = await own_submission(user, found["id"])
        if old and old.get("checked_at"):
            raise HTTPException(409, "already_checked")
        pages = await clean_photos(files)
        base = f"s/{found['id']}/{user['id']}/{uuid.uuid4().hex}"
        keys = [f"{base}/{n + 1}.jpg" for n in range(len(pages))]
        written = []
        try:
            for key, data in zip(keys, pages):
                await call(store().put, key, data)
                written.append(key)
            saved = await call(store().save_submission, {
                "worksheet_id": found["id"], "student_id": user["id"], "student_email": str(user.get("email", "")).lower(),
                "page_keys": keys, "submitted_at": datetime.now(timezone.utc).isoformat()})
        except HTTPException:
            try:
                await run_in_threadpool(store().delete, written)
            except WorksheetsUnavailable:
                pass
            raise
        if old:
            try:
                await run_in_threadpool(store().delete, [k for k in old.get("page_keys") or [] if k not in keys])
            except WorksheetsUnavailable:
                log.warning("a replaced submission's images stayed in storage")
        record(user, "worksheet_submitted", f"{row.get('name', '')}: {found['title']}")
        return reply(submission_public(saved))

    @app.get("/api/math/worksheets/{wid}/submission/pages/{n}")
    async def own_page(wid: str, n: int, user=Depends(signed_in)):
        found, _ = await readable(user, wid)
        sub = await own_submission(user, found["id"])
        if not sub:
            raise HTTPException(404, "submission not found")
        keys = sub.get("page_keys") or []
        return image(await call(store().read, keys[page_index(n, len(keys))]))
