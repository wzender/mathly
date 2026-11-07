"""FastAPI app: uvicorn mathly2.main:app"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .auth import DevAuthenticator, SupabaseAuthenticator, current_user
from .bank import Bank, load_bank
from . import classes
from .config import Settings, load_settings
from .store import InMemoryStore, SupabaseStore

STATIC = Path(__file__).parent / "static"


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

    app.include_router(classes.router)

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    def my_class(user: dict) -> dict | None:
        """The student's class. The first time they sign in, their account is linked to the entry the teacher made."""
        if user["role"] != "student":
            return None
        membership = app.state.store.membership(user["email"])
        if membership and not membership["user_id"]:
            app.state.store.link_user(user["email"], user["id"])
        return {"id": membership["class_id"], "name": membership["class_name"]} if membership else None

    @app.get("/api/me")
    def me(user: dict = Depends(current_user)) -> dict:
        return {"email": user["email"], "role": user["role"], "class": my_class(user)}

    def in_class_or_teacher(user: dict = Depends(current_user)) -> dict:
        if user["role"] == "student" and not app.state.store.membership(user["email"]):
            raise HTTPException(403, "ask your teacher to add you to a class")
        return user

    @app.get("/api/lessons")
    def lessons(user: dict = Depends(in_class_or_teacher)) -> list[dict]:
        return app.state.bank.lessons_with_skills()

    @app.get("/", include_in_schema=False)
    def index() -> HTMLResponse:
        # The browser needs only the public values: the Supabase URL and the publishable key. Never the secret key.
        config = {"supabaseUrl": settings.supabase_url, "supabaseKey": settings.supabase_key,
                  "devSignIn": not settings.supabase_on}
        text = json.dumps(config).replace("<", "\\u003c")
        html = (STATIC / "index.html").read_text(encoding="utf-8").replace("__CONFIG__", text)
        return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app


app = create_app()
