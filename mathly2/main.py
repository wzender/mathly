"""FastAPI app: uvicorn mathly2.main:app"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .access import RoleResolver, learner, permissions_of
from .auth import DevAuthenticator, SupabaseAuthenticator, current_user
from .bank import Bank, load_bank
from . import accounts, classes, quizzes, reads, realtests, skills
from .config import Settings, load_settings
from .store import InMemoryStore, StoreUnavailable, SupabaseStore

STATIC = Path(__file__).parent / "static"


class FreshStaticFiles(StaticFiles):
    """Static files the browser must check before reusing (`no-cache` keeps the ETag, so an unchanged file is a 304):
    after an update every device gets the new styles and scripts without clearing its cache."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache"
        return response
log = logging.getLogger("mathly2")


def create_app(settings: Settings | None = None, bank: Bank | None = None, store=None, authenticator=None) -> FastAPI:
    app = FastAPI(title="Mathly 2")
    app.state.settings = settings = (settings or load_settings()).check()
    app.state.bank = bank or load_bank()   # a broken bank stops the server from starting
    if settings.supabase_on:
        app.state.store = store or SupabaseStore(settings.supabase_url, settings.supabase_secret)
        app.state.authenticator = authenticator or SupabaseAuthenticator(settings.supabase_url, settings.supabase_key)
    else:
        app.state.store = store or InMemoryStore()
        app.state.authenticator = authenticator or DevAuthenticator()

    app.state.roles = RoleResolver(settings, app.state.store)
    @app.exception_handler(StoreUnavailable)
    async def store_unavailable(request: Request, exc: StoreUnavailable) -> JSONResponse:
        log.warning("database problem on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse({"detail": "מסד הנתונים לא ענה או סירב לבקשה. נסו שוב, ואם זה חוזר, בדקו שהמיגרציות הוחלו (ראו את יומן השרת)."}, status_code=503)

    app.include_router(classes.router)
    app.include_router(classes.teaching)
    app.include_router(accounts.router)
    app.include_router(skills.router)
    app.include_router(quizzes.router)
    app.include_router(realtests.router)

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
        everything = app.state.bank.lessons_with_skills()
        if set(user["roles"]) - {"student"}:
            return everything
        mine = {lesson for c in reads.of(request).classes_of_student(user["email"]) for lesson in c["lessons"]}
        return [lesson for lesson in everything if lesson["id"] in mine]

    @app.get("/", include_in_schema=False)
    def index() -> HTMLResponse:
        # The browser needs only the public values: the Supabase URL and the publishable key. Never the secret key.
        config = {"supabaseUrl": settings.supabase_url, "supabaseKey": settings.supabase_key,
                  "devSignIn": not settings.supabase_on}
        text = json.dumps(config).replace("<", "\\u003c")
        html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__CONFIG__", text)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    app.mount("/static", FreshStaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
