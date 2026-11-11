"""Subjects and the lessons kept in the database (add-subjects-and-worksheets). A manager or a developer creates subjects, renames
them and orders their lessons; a developer can load a lesson as JSON. Math is a subject from the start: it owns the content
file's lessons and cannot be renamed or deleted. Every change that students would see rebuilds the served bank (content.py)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import content
from .access import need
from .bank import lesson_problems
from .lessons import assign_ids
from .store import SubjectExists

router = APIRouter(prefix="/api/subjects")

MAX_NAME = 60
ICONS = ("∑", "⚗", "🧬", "🌍", "📖", "🏛", "🎨", "🎵", "💻", "🗣")


class SubjectBody(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    icon: str | None = Field(default=None, max_length=8)


class OrderBody(BaseModel):
    lessons: list[int] = Field(max_length=500)


class LessonBody(BaseModel):
    lesson: dict


def _store(request: Request):
    return request.app.state.store


def _name(raw: str | None) -> str:
    name = " ".join((raw or "").split())
    if not 1 <= len(name) <= MAX_NAME:
        raise HTTPException(422, f"שם המקצוע צריך להיות בין תו אחד ל־{MAX_NAME} תווים")
    return name


def _icon(raw: str | None) -> str:
    if raw not in ICONS:
        raise HTTPException(422, "צריך לבחור סמל מהרשימה")
    return raw


def _subject(request: Request, subject_id: str) -> dict:
    found = next((s for s in _store(request).subjects() if s["id"] == subject_id), None)
    if found is None:
        raise HTTPException(404, "המקצוע לא נמצא")
    return found


def lesson_summary(row: dict) -> dict:
    doc = row["published"] if row["published"] is not None else row["draft"]
    return {"id": row["id"], "name": (row["draft"] or {}).get("name") or (doc or {}).get("name") or "", "published": row["published"] is not None,
            "status": row["status"], "position": row["position"], "skills": len((doc or {}).get("skills") or [])}


@router.get("")
def list_subjects(request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    """Every subject in order with its lessons: math's file lessons (fixed) and the lessons kept in the database."""
    store, bank = _store(request), request.app.state.bank
    by_subject: dict[str, list[dict]] = {}
    for row in store.lessons_of():
        by_subject.setdefault(row["subject_id"], []).append(lesson_summary(row))
    return {"icons": list(ICONS), "content_error": getattr(request.app.state, "content_error", None),
            "subjects": [{**{k: s[k] for k in ("id", "name", "icon")}, "fixed": s["id"] == "math",
                          "file_lessons": [{"id": u["id"], "name": u["name"]} for u in request.app.state.base_bank.lessons] if s["id"] == "math" else [],
                          "lessons": by_subject.get(s["id"], [])} for s in store.subjects()],
            "served_lessons": len(bank.lessons)}


@router.post("", status_code=201)
def create_subject(body: SubjectBody, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    try:
        row = _store(request).create_subject(f"s{uuid.uuid4().hex[:8]}", _name(body.name), user["email"], icon=_icon(body.icon or ICONS[0]))
    except SubjectExists:
        raise HTTPException(409, "כבר יש מקצוע בשם הזה") from None
    content.rebuild(request.app)
    return {k: row[k] for k in ("id", "name", "icon")}


@router.put("/{subject_id}")
def update_subject(subject_id: str, body: SubjectBody, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    _subject(request, subject_id)
    if subject_id == "math":
        raise HTTPException(422, "את מקצוע המתמטיקה אי אפשר לשנות")
    fields = {}
    if body.name is not None:
        fields["name"] = _name(body.name)
    if body.icon is not None:
        fields["icon"] = _icon(body.icon)
    try:
        row = _store(request).update_subject(subject_id, **fields) if fields else _subject(request, subject_id)
    except SubjectExists:
        raise HTTPException(409, "כבר יש מקצוע בשם הזה") from None
    content.rebuild(request.app)
    return {k: row[k] for k in ("id", "name", "icon")}


@router.delete("/{subject_id}", status_code=204)
def delete_subject(subject_id: str, request: Request, user: dict = Depends(need("content.manage"))) -> None:
    """An empty subject can go (its drafts with it); one with a published lesson cannot."""
    _subject(request, subject_id)
    if subject_id == "math":
        raise HTTPException(422, "את מקצוע המתמטיקה אי אפשר למחוק")
    store = _store(request)
    lessons = store.lessons_of(subject_id)
    if any(l["published"] is not None for l in lessons):
        raise HTTPException(409, "במקצוע יש שיעורים שפורסמו. קודם מבטלים את פרסומם, ואז מוחקים את המקצוע")
    for lesson in lessons:
        store.delete_lesson(lesson["id"])
    store.delete_subject(subject_id)
    content.rebuild(request.app)


@router.put("/{subject_id}/order")
def order_lessons(subject_id: str, body: OrderBody, request: Request, user: dict = Depends(need("content.manage"))) -> dict:
    """The subject's lessons kept in the database, in this order (math's file lessons always come first and keep theirs)."""
    _subject(request, subject_id)
    store = _store(request)
    current = {l["id"] for l in store.lessons_of(subject_id)}
    if set(body.lessons) != current or len(body.lessons) != len(current):
        raise HTTPException(422, "הסדר צריך לכלול כל שיעור של המקצוע פעם אחת")
    for position, lesson_id in enumerate(body.lessons, 1):
        store.save_lesson(lesson_id, position=position)
    content.rebuild(request.app)
    return {"lessons": [lesson_summary(l) for l in store.lessons_of(subject_id)]}


@router.post("/{subject_id}/lessons", status_code=201)
def load_lesson(subject_id: str, body: LessonBody, request: Request, user: dict = Depends(need("content.load"))) -> dict:
    """A developer loads a lesson as JSON in the lesson document's shape; it is saved as a draft (not published), its skills and
    mistakes get this lesson's ids, and it must pass the bank's checks."""
    _subject(request, subject_id)
    store = _store(request)
    row = store.create_lesson(subject_id, user["email"], {}, source="json")
    document = assign_ids(body.lesson, row["id"])
    problems = lesson_problems(document, row["id"])
    if problems:
        store.delete_lesson(row["id"])
        raise HTTPException(422, {"message": "השיעור לא עבר את הבדיקות", "problems": problems})
    return lesson_summary(store.save_lesson(row["id"], draft=document)) | {"draft": document}
