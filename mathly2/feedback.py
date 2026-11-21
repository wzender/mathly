"""Suggestions and feedback (משוב): any signed-in person sends an idea, a problem or anything else, with the screen they were on; the
developer reads them on the developer screen and marks them handled. At most DAILY_LIMIT a person a day, so a stuck button cannot flood it."""
from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import clock
from .auth import current_user
from .status import developer

router = APIRouter(prefix="/api")
DAILY_LIMIT = 20


class Feedback(BaseModel):
    kind: Literal["idea", "bug", "other"] = "idea"
    body: str = Field(..., max_length=2000)
    page: str = Field("", max_length=200)


class Handled(BaseModel):
    handled: bool


def _public(row: dict) -> dict:
    return {"id": row["id"], "email": row["email"], "roles": row["roles"], "kind": row["kind"], "body": row["body"], "page": row["page"],
            "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            "handled_at": row["handled_at"].isoformat() if row["handled_at"] else None}


@router.post("/feedback", status_code=201)
def send(body: Feedback, request: Request, user: dict = Depends(current_user)) -> dict:
    """Any signed-in person: one suggestion, problem or remark."""
    text = body.body.strip()
    if not text:
        raise HTTPException(422, "כתבו מה תרצו לספר לנו")
    store, now = request.app.state.store, clock.now()
    if store.feedback_count_since(user["id"], now - timedelta(days=1)) >= DAILY_LIMIT:
        raise HTTPException(429, "שלחתם הרבה הצעות היום. אפשר לשלוח שוב מחר")
    row = store.add_feedback(user["id"], user["email"], sorted(user["roles"]), body.kind, text, body.page.strip(), now)
    return {"id": row["id"]}


@router.get("/feedback")
def read(request: Request, user: dict = Depends(developer)) -> list[dict]:
    """The developer: every suggestion, the newest first."""
    return [_public(r) for r in request.app.state.store.feedback()]


@router.post("/feedback/{feedback_id}/handled")
def mark(feedback_id: int, body: Handled, request: Request, user: dict = Depends(developer)) -> dict:
    row = request.app.state.store.mark_feedback(feedback_id, clock.now() if body.handled else None)
    if row is None:
        raise HTTPException(404, "ההצעה לא נמצאה")
    return _public(row)
