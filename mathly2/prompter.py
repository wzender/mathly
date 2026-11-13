"""The developer's prompter (פרומפטר, change add-prompter, PRD DEV-2): saved texts on every device, and on request the AI's outline.

Developers only, each seeing only their own texts (up to 200; a title up to 120 characters, the text up to 100,000). A text may have an
outline (ראשי פרקים): the AI rewrites it once, on request, as the same slides with two to four very short topic reminders each; it is kept
with the text and can be edited. Changing the text without sending an outline drops the outline, so a stale one is never shown. The
full-screen prompter itself is static/prompter.js (ported as is from mathly1).
"""
from __future__ import annotations

import logging
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import ai
from .status import developer

log = logging.getLogger("mathly2.prompter")
router = APIRouter(prefix="/api/prompter")

MAX_TITLE, MAX_BODY, MAX_TEXTS, MAX_OUTLINE = 120, 100_000, 200, ai.OUTLINE_MAX
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class TextBody(BaseModel):
    title: str = ""
    body: str
    outline: str | None = None          # sent: replaces the outline ("" removes it); not sent: kept only if the text did not change


def _clean(body: TextBody) -> dict:
    if not body.body.strip():
        raise HTTPException(422, "הטקסט ריק")
    if len(body.body) > MAX_BODY:
        raise HTTPException(413, f"הטקסט ארוך מדי (עד {MAX_BODY:,} תווים)")
    title = " ".join(body.title.split()) or " ".join(body.body.strip().splitlines()[0].split())
    return {"title": title[:MAX_TITLE], "body": body.body}


def _outline(value: str | None) -> str | None:
    if value is not None and len(value) > MAX_OUTLINE:
        raise HTTPException(413, f"ראשי הפרקים ארוכים מדי (עד {MAX_OUTLINE:,} תווים)")
    return value if value and value.strip() else None


def _shown(row: dict) -> dict:
    return {"id": row["id"], "title": row["title"], "body": row["body"], "outline": row.get("outline"),
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None}


def _mine(request: Request, user: dict, text_id: str) -> dict:
    row = request.app.state.store.get_prompter_text(user["id"], text_id) if UUID.match(text_id) else None
    if row is None:
        raise HTTPException(404, "הטקסט לא נמצא")
    return row


@router.get("/texts")
def list_texts(request: Request, user: dict = Depends(developer)) -> dict:
    return {"texts": [_shown(t) for t in request.app.state.store.prompter_texts(user["id"])]}


@router.post("/texts", status_code=201)
def add_text(body: TextBody, request: Request, user: dict = Depends(developer)) -> dict:
    store, row = request.app.state.store, _clean(body)
    if len(store.prompter_texts(user["id"])) >= MAX_TEXTS:
        raise HTTPException(409, f"אפשר לשמור עד {MAX_TEXTS} טקסטים. מחקו טקסט ישן ונסו שוב.")
    made = store.add_prompter_text(user["id"], row["title"], row["body"])
    if body.outline is not None and _outline(body.outline):
        made = store.save_prompter_text(user["id"], made["id"], touch=False, outline=_outline(body.outline))
    return {"text": _shown(made)}


@router.put("/texts/{text_id}")
def save_text(text_id: str, body: TextBody, request: Request, user: dict = Depends(developer)) -> dict:
    old = _mine(request, user, text_id)
    fields = _clean(body)
    if "outline" in body.model_fields_set:
        fields["outline"] = _outline(body.outline)
    elif old["body"] != fields["body"]:
        fields["outline"] = None                                 # written from the old text: it goes when the text changes
    return {"text": _shown(request.app.state.store.save_prompter_text(user["id"], text_id, **fields))}


@router.delete("/texts/{text_id}", status_code=204)
def delete_text(text_id: str, request: Request, user: dict = Depends(developer)) -> None:
    _mine(request, user, text_id)
    request.app.state.store.delete_prompter_text(user["id"], text_id)


@router.post("/texts/{text_id}/outline")
def make_outline(text_id: str, request: Request, user: dict = Depends(developer)) -> dict:
    """The AI writes (or rewrites) the text's outline; it is saved with the text. The text's date is left alone: the text did not change."""
    row = _mine(request, user, text_id)
    try:
        result = request.app.state.ai.outline(row["body"])
    except ai.AIFailure as exc:
        what, todo = ai.FAILURES.get(exc.reason, ai.FAILURES["provider_error"])
        log.warning("prompter outline failed: %s (%s)", exc.reason, exc.detail)
        raise HTTPException(503, f"{what}. {todo}") from None
    try:
        if result.get("usage"):
            request.app.state.store.add_ai_usage(ai.usage_row(result["usage"], "prompter", None, user["id"]))
    except Exception as exc:                                     # recording the cost never fails the outline
        log.warning("prompter outline: usage not recorded: %s", type(exc).__name__)
    return {"text": _shown(request.app.state.store.save_prompter_text(user["id"], text_id, touch=False, outline=result["outline"]))}
