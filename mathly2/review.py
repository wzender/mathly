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


def _card(request: Request, item: dict) -> dict | None:
    """A waiting question as the browser may see it (no right choice), with where it is from; None when the bank no longer has it."""
    served = request.app.state.bank.practice_question(item["skill_id"], item["question_key"])
    return None if served is None else {**served, "source": item["source"]}


def _waiting(request: Request, user: dict) -> list[dict]:
    items = request.app.state.store.review_of(user["id"])
    return [i for i in items if request.app.state.bank.practice_question(i["skill_id"], i["question_key"]) is not None]


def _groups(request: Request, items: list[dict]) -> list[dict]:
    """The waiting questions as cards, grouped by skill: the skills in the bank's order, each skill's cards oldest first. A skill with none has no group."""
    bank = request.app.state.bank
    lessons = {l["id"]: l["name"] for l in bank.lessons}
    by_skill: dict[str, list[dict]] = {}
    for item in items:                                                        # `items` is oldest first
        by_skill.setdefault(item["skill_id"], []).append(item)
    groups = []
    for skill in bank.skills:
        if skill["id"] in by_skill:
            cards = [c for c in (_card(request, i) for i in by_skill[skill["id"]]) if c]
            groups.append({"skill": {"id": skill["id"], "name": skill["name"]}, "lesson": {"id": skill["unit"], "name": lessons.get(skill["unit"], "")}, "cards": cards})
    return groups


@router.get("")
def review(request: Request, user: dict = Depends(learner)) -> dict:
    items = _waiting(request, user)
    return {"count": len(items), "groups": _groups(request, items)}


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
    return {"correct": graded["correct"], "mistake": mistake, "count": len(items), "skill_count": sum(1 for i in items if i["skill_id"] == item["skill_id"])}
