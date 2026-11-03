"""The student's path progress, kept with the account so it follows them to every device.

The page keeps its progress (P in static/math.js) on the device and sends a copy here after each change. A device
that opens the app reads this copy and merges it with its own (the merge rules are in math.js), so work done on
either device is kept. The server only stores the object: one row per account in the Supabase table `math_progress`,
read and written with the server's secret key.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from .auth import AuthUnavailable

log = logging.getLogger("mathly.progress")
MAX_BYTES = 1_000_000
MIGRATION = "supabase/migrations/20261103200000_math_progress.sql"
TABLE = "/rest/v1/math_progress"


def load_progress(auth, user_id: str) -> dict:
    rows = auth._admin(f"{TABLE}?select=data&user_id=eq.{user_id}") or []
    return rows[0]["data"] if rows and isinstance(rows[0].get("data"), dict) else {}


def save_progress(auth, user_id: str, data: dict) -> None:
    auth._admin(f"{TABLE}?on_conflict=user_id", "POST",
                {"user_id": user_id, "data": data, "updated_at": datetime.now(timezone.utc).isoformat()},
                prefer="resolution=merge-duplicates,return=minimal")


def install_progress_routes(app, signed_in):
    """GET and PUT /api/math/progress: the signed-in student's progress."""
    def account(user=Depends(signed_in)) -> str:
        if not user or not user.get("id"):
            raise HTTPException(401, "sign_in_required")
        return user["id"]

    def unavailable(exc: AuthUnavailable) -> HTTPException:
        if "answered 404" in str(exc):
            log.warning("the math_progress table is missing; apply %s", MIGRATION)
        else:
            log.error("progress not synced: %s", exc)
        return HTTPException(503, "progress_unavailable")

    @app.get("/api/math/progress")
    def get_progress(user: str = Depends(account)):
        try:
            data = load_progress(app.state.auth, user)
        except AuthUnavailable as exc:
            raise unavailable(exc) from exc
        return JSONResponse({"progress": data}, headers={"Cache-Control": "no-store"})

    @app.put("/api/math/progress")
    async def put_progress(request: Request, user: str = Depends(account)):
        raw = await request.body()
        if len(raw) > MAX_BYTES:
            raise HTTPException(413, "progress_too_large")
        try:
            data = json.loads(raw).get("progress")
        except (ValueError, AttributeError) as exc:
            raise HTTPException(400, "send {\"progress\": {...}}") from exc
        if not isinstance(data, dict):
            raise HTTPException(400, "send {\"progress\": {...}}")
        try:
            save_progress(app.state.auth, user, data)
        except AuthUnavailable as exc:
            raise unavailable(exc) from exc
        return {"ok": True}
