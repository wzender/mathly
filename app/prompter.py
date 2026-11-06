"""The prompter's saved texts (ניהול ← פרומפטר, static/prompter.js), kept with the account so they are on every device.

For developers only (the management.access permission, like the rest of ניהול). Each account sees only its own texts.
They are kept in the Supabase table `math_prompter_texts`, read and written with the server's secret key.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from datetime import datetime, timezone

from fastapi import Body, Depends, HTTPException
from fastapi.responses import JSONResponse

from .access import has_permission
from .auth import AuthUnavailable

log = logging.getLogger("mathly.prompter")
MIGRATION = "supabase/migrations/20261106130000_math_prompter_texts.sql"
TABLE = "/rest/v1/math_prompter_texts"
MAX_TITLE, MAX_BODY, MAX_TEXTS = 120, 100_000, 200
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
FIELDS = "id,title,body,updated_at"


def clean(body: dict) -> dict:
    """The title and text from a request, or HTTPException 400. An empty title becomes the text's first line."""
    if not isinstance(body, dict):
        raise HTTPException(400, "send {\"title\": ..., \"body\": ...}")
    text, title = body.get("body"), body.get("title", "")
    if not isinstance(text, str) or not isinstance(title, str):
        raise HTTPException(400, "send {\"title\": ..., \"body\": ...}")
    if not text.strip():
        raise HTTPException(400, "empty_text")
    if len(text) > MAX_BODY:
        raise HTTPException(413, "text_too_long")
    title = " ".join(title.split()) or " ".join(text.strip().splitlines()[0].split())
    return {"title": title[:MAX_TITLE], "body": text}


def install_prompter_routes(app, signed_in):
    """GET/POST /api/prompter/texts and PUT/DELETE /api/prompter/texts/{id}: the developer's own saved texts."""
    def developer(user=Depends(signed_in)) -> str:
        if not user or not user.get("id"):
            raise HTTPException(401, "sign_in_required")
        if not has_permission(user, "management.access"):
            raise HTTPException(403, "developers_only")
        return user["id"]

    def admin(path: str, method: str = "GET", body=None, prefer: str = "return=representation"):
        try:
            return app.state.auth._admin(path, method, body, prefer=prefer)
        except AuthUnavailable as exc:
            if "answered 404" in str(exc):
                log.warning("the math_prompter_texts table is missing; apply %s", MIGRATION)
            else:
                log.error("prompter texts unavailable: %s", exc)
            raise HTTPException(503, "prompter_unavailable") from exc

    def one(text_id: str, user: str) -> str:
        if not UUID.match(text_id):
            raise HTTPException(404, "not_found")
        return urllib.parse.urlencode({"id": f"eq.{text_id}", "user_id": f"eq.{user}"})

    def now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @app.get("/api/prompter/texts")
    def list_texts(user: str = Depends(developer)):
        rows = admin(f"{TABLE}?select={FIELDS}&order=updated_at.desc&limit={MAX_TEXTS}&"
                     + urllib.parse.urlencode({"user_id": f"eq.{user}"})) or []
        return JSONResponse({"texts": rows}, headers={"Cache-Control": "no-store"})

    @app.post("/api/prompter/texts")
    def add_text(body: dict = Body(...), user: str = Depends(developer)):
        row = clean(body)
        have = admin(f"{TABLE}?select=id&limit={MAX_TEXTS}&" + urllib.parse.urlencode({"user_id": f"eq.{user}"})) or []
        if len(have) >= MAX_TEXTS:
            raise HTTPException(409, "too_many_texts")
        rows = admin(f"{TABLE}?select={FIELDS}", "POST", {**row, "user_id": user, "updated_at": now()}) or []
        return {"text": rows[0] if rows else None}

    @app.put("/api/prompter/texts/{text_id}")
    def save_text(text_id: str, body: dict = Body(...), user: str = Depends(developer)):
        row = clean(body)
        rows = admin(f"{TABLE}?select={FIELDS}&" + one(text_id, user), "PATCH", {**row, "updated_at": now()}) or []
        if not rows:
            raise HTTPException(404, "not_found")
        return {"text": rows[0]}

    @app.delete("/api/prompter/texts/{text_id}")
    def delete_text(text_id: str, user: str = Depends(developer)):
        admin(f"{TABLE}?" + one(text_id, user), "DELETE", prefer="return=minimal")
        return {"ok": True}
