"""The review tab (חזרה, PRD STU-8): every wrong answer waits here to be redone, one question at a time. A right answer removes the question; a wrong
one keeps it and names the mistake and its tip, never the right choice. It is practice only: nothing here touches mastery, a grade, the readiness
meter or a practice round (the answers go to their own tables); each right answer counts toward the daily goal."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import clock
from .access import learner

router = APIRouter(prefix="/api/review")


class Redo(BaseModel):
    key: str
    choice: int


def _question(request: Request, item: dict) -> dict | None:
    """A waiting question as the browser may see it (no right choice), with where it is from; None when the bank no longer has it."""
    bank = request.app.state.bank
    served = bank.practice_question(item["skill_id"], item["question_key"])
    skill = bank.skill(item["skill_id"])
    if served is None or skill is None:
        return None
    lesson = next((l for l in bank.lessons if l["id"] == skill["unit"]), None)
    return {**served, "skill": {"id": skill["id"], "name": skill["name"]}, "lesson": {"id": skill["unit"], "name": lesson["name"] if lesson else ""},
            "source": item["source"]}


def _waiting(request: Request, user: dict) -> list[dict]:
    items = request.app.state.store.review_of(user["id"])
    return [i for i in items if request.app.state.bank.practice_question(i["skill_id"], i["question_key"]) is not None]


def _pick(request: Request, items: list[dict], avoid: str | None) -> dict | None:
    """The oldest waiting question; never the one just answered while others wait."""
    others = [i for i in items if i["question_key"] != avoid]
    chosen = (others or items)[:1]
    return _question(request, chosen[0]) if chosen else None


@router.get("")
def review(request: Request, after: str | None = None, user: dict = Depends(learner)) -> dict:
    items = _waiting(request, user)
    return {"count": len(items), "question": _pick(request, items, after)}


@router.post("/answer")
def redo(body: Redo, request: Request, user: dict = Depends(learner)) -> dict:
    bank, store = request.app.state.bank, request.app.state.store
    items = _waiting(request, user)
    item = next((i for i in items if i["question_key"] == body.key), None)
    if item is None:
        raise HTTPException(409, "השאלה הזו כבר לא ברשימת החזרה")
    graded = bank.grade(item["skill_id"], body.key, body.choice)
    if graded is None:
        raise HTTPException(422, "תשובה לא חוקית")
    mistake = None
    if graded["correct"]:
        store.remove_review(user["id"], body.key)
        store.add_review_done(user["id"], body.key, clock.school_day())        # the daily goal counts it; mastery and rounds do not
        items = [i for i in items if i["question_key"] != body.key]
    elif graded["mistake"]:
        found = graded["mistake"]
        back = bank.skill(found["back"]) if found["back"] else None
        mistake = {"name": found["name"], "tip": found["tip"], "back": found["back"], "back_name": back["name"] if back else None}
    return {"correct": graded["correct"], "mistake": mistake, "count": len(items), "next": _pick(request, items, body.key)}
