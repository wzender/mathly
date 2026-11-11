"""The developer's status card: is each part of the system working, which version runs and since when (PRD DEV-5).

Only a developer may read it. Nothing here returns a key or a secret: a setting is reported as set or not set."""
from __future__ import annotations

import platform
import time

from fastapi import APIRouter, Depends, Request

from . import clock, version
from .access import need

router = APIRouter(prefix="/api/dev")

OK, WARN, ERROR, OFF = "ok", "warn", "error", "off"


def _check(key: str, name: str, state: str, detail: str) -> dict:
    return {"key": key, "name": name, "state": state, "detail": detail}


def _database(store, supabase_on: bool) -> dict:
    if not supabase_on:
        return _check("database", "מסד הנתונים", WARN, "זיכרון בלבד: שום דבר לא נשמר אחרי הפעלה מחדש")
    raw = getattr(store, "_store", store)                  # past the cache, so the database itself answers
    started = time.monotonic()
    try:
        raw.roles_of("status-check@mathly.invalid")
    except Exception as exc:                                # any failure is the answer, not a crash of the card
        return _check("database", "מסד הנתונים", ERROR, f"לא ענה ({type(exc).__name__})")
    return _check("database", "מסד הנתונים", OK, f"Supabase ענה תוך {round((time.monotonic() - started) * 1000)} אלפיות שנייה")


def checks(app) -> list[dict]:
    s, state = app.state.settings, app.state
    bank = state.bank
    return [
        _database(state.store, s.supabase_on),
        _check("sign_in", "התחברות", OK if s.supabase_on else WARN,
               "Google דרך Supabase" if s.supabase_on else "כניסת פיתוח עם כתובת מייל בלבד"),
        _check("bank", "מאגר השאלות", OK, f"{len(bank.lessons)} שיעורים, {len(bank.skills)} מיומנויות"),
        _check("ai", "עזרת AI", OK if s.anthropic_key else OFF, "מפתח מוגדר" if s.anthropic_key else "אין מפתח: העזרה כבויה"),
        _check("push", "התראות לטלפון", OK if s.vapid_private_key else OFF,
               "מפתח מוגדר" if s.vapid_private_key else "אין מפתח: ההתראות כבויות"),
        _check("pictures", "תמונות תשובה", OK if s.supabase_on else WARN,
               f"דלי פרטי {s.answer_bucket}" if s.supabase_on else "בזיכרון בלבד"),
        _check("cleanup", "ניקוי שעתי", OK if getattr(state, "cleanup_stop", None) else OFF,
               "פועל" if getattr(state, "cleanup_stop", None) else "לא פועל בלי Supabase"),
    ]


def overall(found: list[dict]) -> str:
    states = {c["state"] for c in found}
    return ERROR if ERROR in states else WARN if WARN in states else OK


@router.get("/status")
def status(request: Request, user: dict = Depends(need("dev.status"))) -> dict:
    app = request.app
    found = checks(app)
    now = clock.now()
    started = app.state.started_at
    return {"overall": overall(found), "checks": found, "version": app.state.version,
            "started_at": started.isoformat(), "uptime_seconds": max(0, int((now - started).total_seconds())), "now": now.isoformat(),
            "python": platform.python_version()}


def setup(app) -> None:
    app.state.version = version.read()
    app.state.started_at = clock.now()
    app.include_router(router)
