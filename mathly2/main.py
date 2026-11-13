"""FastAPI app: uvicorn mathly2.main:app"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .access import RoleResolver, learner, permissions_of
from .auth import DevAuthenticator, SupabaseAuthenticator, current_user
from .bank import Bank, load_bank

from . import accounts, ai, ai_help, assignments, classes, cleanup, content, progress, quizzes, reads, realtests, review, rounds, skills, status, subjects, worksheets, written
from .config import Settings, load_settings
from .cached import CachedStore
from .store import InMemoryStore, StoreUnavailable, SupabaseStore
from .pictures import MemoryPictures, PictureError, SupabasePictures
from .push import Pusher, default_subject

STATIC = Path(__file__).parent / "static"


class FreshStaticFiles(StaticFiles):
    """Static files the browser must check before reusing (`no-cache` keeps the ETag, so an unchanged file is a 304):
    after an update every device gets the new styles and scripts without clearing its cache."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response
log = logging.getLogger("mathly2")


def create_app(settings: Settings | None = None, bank: Bank | None = None, store=None, authenticator=None, picture_store=None, pusher=None, ai_client=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        # Against the real database the pictures are tidied every hour (nothing runs without Supabase, so local runs and tests are quiet).
        stop = cleanup.start_hourly(application.state.store, application.state.pictures) if application.state.settings.supabase_on else None
        application.state.cleanup_stop = stop
        ai_help.requeue_after_restart(application.state.store)     # a request that was being processed when the server stopped waits again
        worksheets.recover_after_restart(application.state.store)  # a worksheet left drafting can be tried again
        yield
        if stop:
            stop.set()

    app = FastAPI(title="Mathly 2", lifespan=lifespan)
    app.state.settings = settings = (settings or load_settings()).check()
    app.state.bank = bank or load_bank()   # a broken bank stops the server from starting
    if settings.supabase_on:
        app.state.store = store or CachedStore(SupabaseStore(settings.supabase_url, settings.supabase_secret), settings.cache_seconds)
        app.state.authenticator = authenticator or SupabaseAuthenticator(settings.supabase_url, settings.supabase_key)
    else:
        app.state.store = store or InMemoryStore()
        app.state.authenticator = authenticator or DevAuthenticator()

    app.state.pictures = picture_store or (SupabasePictures(settings.supabase_url, settings.supabase_secret, settings.answer_bucket)
                                           if settings.supabase_on else MemoryPictures())
    app.state.pusher = pusher or Pusher(app.state.store, settings.vapid_private_key, default_subject(settings))
    app.state.notify_request = written.notify_new_request
    app.state.ai = ai_client or ai.make_ai(settings)
    app.state.worksheet_files = (SupabasePictures(settings.supabase_url, settings.supabase_secret, "m2-worksheets")
                                 if settings.supabase_on else MemoryPictures())
    app.state.run_worksheet = worksheets.submit                 # drafting in the background (tests may run it inline)
    app.state.base_bank = app.state.bank          # the content file's lessons; the served bank adds the published ones
    content.rebuild(app)
    app.state.roles = RoleResolver(settings, app.state.store)
    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(request: Request, exc: StoreUnavailable) -> JSONResponse:
        log.warning("database problem on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse({"detail": "מסד הנתונים לא ענה או סירב לבקשה. נסו שוב, ואם זה חוזר, בדקו שהמיגרציות הוחלו (ראו את יומן השרת)."}, status_code=503)

    @app.exception_handler(PictureError)
    async def picture_trouble(request: Request, exc: PictureError) -> JSONResponse:
        return JSONResponse({"detail": written.MESSAGES.get(exc.code, exc.code)}, status_code=exc.status)

    app.include_router(classes.router)
    app.include_router(classes.teaching)
    app.include_router(classes.curriculum)
    app.include_router(accounts.router)
    app.include_router(skills.router)
    app.include_router(rounds.router)
    app.include_router(quizzes.router)
    app.include_router(realtests.router)
    app.include_router(progress.router)
    app.include_router(ai_help.router)
    app.include_router(review.router)
    app.include_router(written.router)
    app.include_router(assignments.router)
    app.include_router(subjects.router)
    app.include_router(worksheets.router)
    status.setup(app)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    @app.get("/api/me")
    def me(request: Request, user: dict = Depends(current_user)) -> dict:
        """Who I am: roles, what they allow, the classes I am a student in and the classes I teach.
        The first time a student signs in, their account is linked to the entries a manager or teacher made for their email."""
        store, here = app.state.store, reads.of(request)
        here.prefetch(("classes_of_student", user["email"]), ("classes_taught", user["email"]))
        classes_as_student = here.classes_of_student(user["email"])
        if classes_as_student:
            store.link_user(user["email"], user["id"])
        return {"email": user["email"], "roles": user["roles"], "permissions": sorted(permissions_of(user["roles"])),
                "classes": [{"id": c["id"], "name": c["name"]} for c in classes_as_student],
                "teaching": [{"id": c["id"], "name": c["name"]} for c in here.classes_taught(user["email"])]}

    @app.get("/api/lessons")
    def lessons(request: Request, user: dict = Depends(learner)) -> list[dict]:
        """The lessons of the student's classes; a teacher or developer sees every lesson."""
        from .skills import visible_lesson_ids
        shown = visible_lesson_ids(request, user)
        return [l for l in app.state.bank.lessons_with_skills() if shown is None or l["id"] in shown]

    @app.get("/", include_in_schema=False)
    def index() -> HTMLResponse:
        # The browser needs only the public values: the Supabase URL and the publishable key. Never the secret key.
        config = {"supabaseUrl": settings.supabase_url, "supabaseKey": settings.supabase_key,
                  "devSignIn": not settings.supabase_on}
        text = json.dumps(config).replace("<", "\\u003c")
        html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__CONFIG__", text)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    @app.get("/service-worker.js", include_in_schema=False)
    def service_worker() -> FileResponse:
        # served from the root so it covers the whole app; the browser must check it for changes each time
        return FileResponse(STATIC / "service-worker.js", media_type="text/javascript",
                            headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})

    app.mount("/static", FreshStaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
