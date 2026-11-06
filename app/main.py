"""Math-only HTTP service for the Mathly algebra path."""
from __future__ import annotations

import base64
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from . import ai_usage
from .ai_queue import MAX_OPEN, for_student, install_ai_queue_routes, may_send
from .access import has_permission, resolve_access
from .answer_routes import install_answer_routes, open_ended_locked
from .answer_scans import ScanError, clean_image
from .auth import AuthUnavailable, ClassConflict, SupabaseAuth, load_auth
from .math_photo import (DAILY_PHOTOS, MAX_PHOTO, MEDIA_TYPES as PHOTO_TYPES,
                         PhotoSolver, PhotoUnavailable, math_model, photo_client)
from .math_skills import algebra9, practice_graph
from .class_report import install_class_report_routes, install_exam_topic_routes
from .teacher_review import install_teacher_review_routes
from .assignments import install_assignment_routes
from .progress import install_progress_routes
from .push import install_push_routes
from .monitoring import ActionLog, RETURN_GAP, install_monitoring_routes
from .unit_resources import install_resource_routes
from .worksheets import install_worksheet_routes
from .quiz_modes import install_quiz_mode_routes
from .student_views import install_student_view_routes
from .ai_batches import install_ai_batch_routes
from .teacher_inbox import install_teacher_inbox_routes
from .teacher_ai import MESSAGE as TEACHER_AI_MESSAGE, LimitReached, TeacherQuota
from .science import install_science_routes

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mathly")
ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
LOCAL_TZ = ZoneInfo("Asia/Jerusalem")
SUBJECT = "מתמטיקה"
load_dotenv(ROOT / ".env")


def units_of(row: dict) -> list[str]:
    """A class's units. A unit split off an older one (its `from`) comes with it, so saved classes keep their content."""
    units = algebra9()["units"]
    known = [unit["id"] for unit in units]
    selected = set(row.get("lessons") or known)
    selected |= {unit["id"] for unit in units if selected & set(unit.get("from", []))}
    return [unit for unit in known if unit in selected]


class FreshStatic(StaticFiles):
    """Static files the browser checks with the server before reusing, so a new deploy shows up on the next visit."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


def create_app(auth: SupabaseAuth | None = None) -> FastAPI:
    """Build the Mathly application."""
    app = FastAPI(title="Mathly")
    app.state.auth = auth or load_auth()
    app.state.photo = None
    app.state.photo_key = None
    app.state.seen = {}
    app.state.actions = ActionLog()
    app.state.photo_counts = {}
    app.state.teacher_ai = TeacherQuota()   # a teacher's 3 AI requests a day (app/teacher_ai.py)
    app.mount("/static", FreshStatic(directory=STATIC), name="static")

    async def signed_in(request: Request) -> dict | None:
        store: SupabaseAuth | None = app.state.auth
        if store is None:
            return None
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise HTTPException(401, "sign in required")
        try:
            user = resolve_access(store, token.strip())
        except AuthUnavailable as exc:
            raise HTTPException(503, f"sign-in check failed: {exc}") from exc
        if user is None:
            raise HTTPException(401, "sign in required")
        if user.get("denied"):
            raise HTTPException(403, "this account is not in a math class")
        key, now = user.get("id") or user.get("email", ""), time.time()
        if now - app.state.seen.get(key, 0) > RETURN_GAP:
            app.state.actions.record(user, "visit")
        app.state.seen[key] = now  # for Monitoring's "signed in lately"
        return user

    async def manager(user: dict | None = Depends(signed_in)) -> dict:
        if not has_permission(user, "management.access"):
            raise HTTPException(403, "management permission required")
        return user

    def page() -> HTMLResponse:
        html = (STATIC / "index.html").read_text(encoding="utf-8")
        store = app.state.auth
        html = html.replace("__SUPABASE_URL__", store.url if store else "")
        html = html.replace("__SUPABASE_KEY__", store.key if store else "")
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @app.get("/", response_class=HTMLResponse)
    @app.get("/math", response_class=HTMLResponse, include_in_schema=False)
    async def index():
        return page()

    @app.get("/service-worker.js", include_in_schema=False)
    async def service_worker():
        # Push notifications only (see app/push.py). It serves nothing from a cache: an older version kept /static/
        # in its own cache forever, so on activation this one also deletes every cache that version left.
        return Response((STATIC / "service-worker.js").read_text(encoding="utf-8"), media_type="text/javascript",
                        headers={"Cache-Control": "no-store"})

    @app.get("/manifest.webmanifest", include_in_schema=False)
    async def manifest():
        return Response((STATIC / "manifest.webmanifest").read_text(encoding="utf-8"),
                        media_type="application/manifest+json")

    @app.get("/api/health")
    async def health():
        return {"ok": True, "app": "mathly"}

    @app.get("/api/me")
    async def me(user: dict | None = Depends(signed_in)):
        mine = (user or {}).get("classes", [])
        email = (user or {}).get("email", "")
        return {"email": email, "user_id": (user or {}).get("id"),
                "answer_scans": app.state.answers.configured,
                "roles": (user or {}).get("roles", []),
                "permissions": (user or {}).get("permissions", []),
                "teacher": bool((user or {}).get("teacher")),
                # the AI: this account sends to it itself (ai_direct), or asks its teacher (app/ai_queue.py);
                # ai_review: it reviews students' requests
                "ai_direct": may_send(user),
                "ai_left": app.state.teacher_ai.left(user),   # a teacher's AI requests left today; None: no limit
                "ai_review": bool(user) and may_send(user) and (
                    has_permission(user, "management.access")
                    or any(email.lower() in (row.get("teachers") or []) for row in mine)),
                "classes": [{"id": row["id"], "name": row["name"], "lessons": units_of(row),
                             "exams": row.get("exams") or [], "exam_note": row.get("exam_note") or "",
                             "exam_title": row.get("exam_title") or "",
                             "teacher": email.lower() in (row.get("teachers") or []),
                             # for the teacher's classes card: how many students (the class's teachers left out)
                             **({"students": len(set(row.get("emails") or []) - set(row.get("teachers") or []))}
                                if email.lower() in (row.get("teachers") or []) else {})} for row in mine]}

    @app.get("/api/math/skills")
    async def math_skills():
        return JSONResponse(practice_graph(app.state.answers.configured, open_ended_locked()),
                            headers={"Cache-Control": "no-store"})

    @app.get("/api/classes")
    async def classes(_user: dict = Depends(manager)):
        try:
            return {"classes": [{**row, "lessons": units_of(row)}
                                for row in app.state.auth.classes(fresh=True)]}
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc

    def save_class(class_id: int | None, body: dict):
        name = " ".join(str(body.get("name") or "").split())
        if not name or len(name) > 80:
            raise HTTPException(400, "class name is required (up to 80 characters)")
        known = [unit["id"] for unit in algebra9()["units"]]
        selected = [unit for unit in known if unit in set(body.get("lessons") or known)]
        if not selected:
            raise HTTPException(400, "choose at least one math unit")
        raw = body.get("emails", "")
        parts = raw.replace(",", " ").split() if isinstance(raw, str) else raw
        emails = sorted({str(part).strip().lower() for part in parts if str(part).strip()})
        # the class has at most one teacher, a free email of its own: a teacher is never also a student
        teachers = sorted({str(t).strip().lower() for t in body.get("teachers") or [] if str(t).strip()})
        if len(teachers) > 1 or any("@" not in t for t in teachers):
            raise HTTPException(400, "a class has one teacher, given by email")
        if set(teachers) & set(emails):
            raise HTTPException(400, "a teacher cannot also be a student of the class")
        try:
            app.state.auth.save_class(class_id, name, emails, {}, selected, teachers=teachers)
        except ClassConflict as exc:
            raise HTTPException(409, "a class with that name already exists") from exc
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(404, "class not found") from exc
        return {"ok": True, "id": class_id, "name": name, "lessons": selected}

    @app.post("/api/classes")
    async def create_class(body: dict, user: dict = Depends(manager)):
        result = save_class(None, body)
        app.state.actions.record(user, "class_saved", f"נפתחה: {result['name']}")
        return result

    @app.put("/api/classes/{class_id}")
    async def update_class(class_id: int, body: dict, user: dict = Depends(manager)):
        result = save_class(class_id, body)
        app.state.actions.record(user, "class_saved", f"נערכה: {result['name']}")
        return result

    @app.delete("/api/classes/{class_id}")
    async def delete_class(class_id: int, user: dict = Depends(manager)):
        try:
            name = next((row["name"] for row in app.state.auth.classes() if row.get("id") == class_id), f"#{class_id}")
            app.state.auth.delete_class(class_id)
            app.state.actions.record(user, "class_deleted", name)
        except AuthUnavailable as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"ok": True}

    photo_counts: dict[tuple[str, str], int] = app.state.photo_counts

    def solver() -> PhotoSolver:
        key = os.environ.get("ANTHROPIC_API_KEY", "").strip() or os.environ.get("CLAUDE_API_KEY", "").strip()
        if not key:
            raise HTTPException(503, "photographed-problem help is not configured")
        if app.state.photo_key != key:
            app.state.photo = PhotoSolver(photo_client(key), math_model(), algebra9()["skills"])
            app.state.photo_key = key
        return app.state.photo

    # the teacher's AI queue sends a student's photo with this (app/ai_queue.py)
    def solve_for_queue(image: bytes, media_type: str) -> dict:
        try:
            service = solver()
        except HTTPException as exc:
            raise PhotoUnavailable("פתרון מתמונה לא זמין כרגע.", "missing_key", "ANTHROPIC_API_KEY is not set") from exc
        return service.solve(image, media_type)
    app.state.solve_photo = solve_for_queue

    @app.post("/api/math/photo")
    async def solve_photo(photo: UploadFile = File(...), user: dict | None = Depends(signed_in)):
        if not may_send(user):
            return await ask_teacher(photo, user)
        return await solve_upload(photo, user)

    async def ask_teacher(photo: UploadFile, user: dict):
        """A student's photo waits in their teacher's AI queue; the teacher sends it to the AI."""
        queue = app.state.ai_queue
        if not queue.configured:
            raise HTTPException(503, "עזרה בצילום אינה זמינה כרגע.")
        counter = (user["email"].lower(), datetime.now(LOCAL_TZ).date().isoformat())
        if photo.content_type not in PHOTO_TYPES:
            raise HTTPException(415, "send a JPEG, PNG, or WebP image")
        raw = await photo.read(MAX_PHOTO + 1)
        if not raw:
            raise HTTPException(400, "the image is empty")
        if len(raw) > MAX_PHOTO:
            raise HTTPException(413, "the image is too large")
        if photo_counts.get(counter, 0) >= DAILY_PHOTOS:
            raise HTTPException(429, "daily photo limit reached")
        try:
            if await run_in_threadpool(queue.open_count, user["id"]) >= MAX_OPEN:
                raise HTTPException(429, "כבר יש לכם כמה בקשות שמחכות למורה. חכו שהמורה יענה עליהן.")
            image = await run_in_threadpool(clean_image, raw, photo.content_type)   # also drops the photo's metadata
            row = await run_in_threadpool(queue.add, {
                "user_id": user["id"], "email": user["email"].lower(), "kind": "photo",
                "image": base64.standard_b64encode(image).decode("ascii")})
        except ScanError as exc:
            if exc.code.endswith("image"):
                raise HTTPException(415, "לא הצלחנו לקרוא את התמונה. צלמו שוב.") from exc
            raise HTTPException(503, "עזרה בצילום אינה זמינה כרגע.") from exc
        photo_counts[counter] = photo_counts.get(counter, 0) + 1
        app.state.actions.record(user, "ai_request", "תרגיל מצולם")
        return {"queued": True, "request": for_student(row), "left": DAILY_PHOTOS - photo_counts[counter]}

    async def solve_upload(photo: UploadFile, user: dict | None):
        service = solver()
        email = (user or {}).get("email", "").lower()
        exempt = "developer" in (user or {}).get("roles", ())
        counter = (email, datetime.now(LOCAL_TZ).date().isoformat()) if email and not exempt else None
        if photo.content_type not in PHOTO_TYPES:
            raise HTTPException(415, "send a JPEG, PNG, or WebP image")
        image = await photo.read(MAX_PHOTO + 1)
        if not image:
            raise HTTPException(400, "the image is empty")
        if len(image) > MAX_PHOTO:
            raise HTTPException(413, "the image is too large")
        if counter and photo_counts.get(counter, 0) >= DAILY_PHOTOS:
            raise HTTPException(429, "daily photo limit reached")
        try:
            quota = app.state.teacher_ai.take(user)
        except LimitReached as exc:
            raise HTTPException(429, TEACHER_AI_MESSAGE) from exc
        if counter:
            photo_counts[counter] = photo_counts.get(counter, 0) + 1
        try:
            result = await run_in_threadpool(service.solve, image, photo.content_type)
        except PhotoUnavailable as exc:
            if counter:
                photo_counts[counter] -= 1
            app.state.teacher_ai.give_back(quota)
            raise HTTPException(503, str(exc)) from exc
        except Exception:
            if counter:
                photo_counts[counter] -= 1
            app.state.teacher_ai.give_back(quota)
            raise
        ai_usage.record(app.state.auth, (user or {}).get("id"), "photo", result.pop("usage", None))
        if not result.get("readable"):
            if counter:
                photo_counts[counter] -= 1
            app.state.teacher_ai.give_back(quota)
        skill = next((s["name"] for s in algebra9()["skills"] if s["id"] == result.get("skill")), "")
        app.state.actions.record(user, "photo", skill if result.get("readable") else "התמונה לא נקראה")
        return {**result, "left": DAILY_PHOTOS - photo_counts.get(counter, 0) if counter else None}

    install_progress_routes(app, signed_in)
    install_class_report_routes(app, signed_in, units_of)
    install_exam_topic_routes(app, signed_in, units_of)
    install_push_routes(app, signed_in)
    install_answer_routes(app, signed_in)
    install_quiz_mode_routes(app, signed_in, units_of)
    install_ai_queue_routes(app, signed_in)
    install_ai_batch_routes(app, signed_in)
    install_teacher_inbox_routes(app, signed_in)
    install_teacher_review_routes(app, signed_in)
    install_assignment_routes(app, signed_in, units_of)
    install_worksheet_routes(app, signed_in)
    install_resource_routes(app, signed_in, units_of)
    install_student_view_routes(app, signed_in, units_of)
    install_science_routes(app)
    install_monitoring_routes(app, manager)
    return app


app = create_app()
