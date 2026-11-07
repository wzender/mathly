"""A teacher's classes and their students."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import EMAIL, teacher_only
from .store import ClassExists, MemberExists

MAX_EMAILS = 200
router = APIRouter(prefix="/api/classes")


class NewClass(BaseModel):
    name: str = Field(max_length=200)


class NewStudents(BaseModel):
    emails: str = Field(max_length=20000)   # pasted text: addresses separated by spaces, commas, semicolons or new lines


def parse_emails(text: str) -> tuple[list[str], list[str]]:
    """(valid, invalid) addresses from pasted text: lower-case, without repeats, in the order given."""
    valid: list[str] = []
    invalid: list[str] = []
    for part in re.split(r"[\s,;]+", text.strip().lower()):
        if not part:
            continue
        bucket = valid if EMAIL.match(part) and len(part) <= 254 else invalid
        if part not in bucket:
            bucket.append(part)
    return valid, invalid


def own_class(request: Request, class_id: int, user: dict) -> dict:
    row = request.app.state.store.get_class(class_id)
    if not row or row["teacher_email"] != user["email"]:
        raise HTTPException(404, "הכיתה לא נמצאה")
    return row


@router.get("")
def list_classes(request: Request, user: dict = Depends(teacher_only)) -> list[dict]:
    return [{"id": c["id"], "name": c["name"], "students": c["students"]}
            for c in request.app.state.store.classes_of(user["email"])]


@router.post("", status_code=201)
def create_class(body: NewClass, request: Request, user: dict = Depends(teacher_only)) -> dict:
    name = " ".join(body.name.split())
    if not 1 <= len(name) <= 60:
        raise HTTPException(422, "שם הכיתה צריך להיות בין תו אחד ל־60 תווים")
    try:
        row = request.app.state.store.create_class(user["email"], name)
    except ClassExists:
        raise HTTPException(409, "כבר יש לך כיתה בשם הזה") from None
    return {"id": row["id"], "name": row["name"], "students": 0}


@router.get("/{class_id}")
def show_class(class_id: int, request: Request, user: dict = Depends(teacher_only)) -> dict:
    row = own_class(request, class_id, user)
    members = request.app.state.store.members(class_id)
    return {"id": row["id"], "name": row["name"],
            "students": [{"email": m["email"], "signed_in": bool(m["user_id"])} for m in members]}


@router.post("/{class_id}/students")
def add_students(class_id: int, body: NewStudents, request: Request, user: dict = Depends(teacher_only)) -> dict:
    own_class(request, class_id, user)
    store = request.app.state.store
    valid, invalid = parse_emails(body.emails)
    if len(valid) > MAX_EMAILS:
        raise HTTPException(422, f"אפשר להוסיף עד {MAX_EMAILS} תלמידים בכל פעם")
    result: dict = {"added": [], "already_here": [], "elsewhere": [], "invalid": invalid}
    for email in valid:
        current = store.membership(email)
        if current is None:
            try:
                store.add_member(class_id, email)
                result["added"].append(email)
                continue
            except MemberExists:   # added to another class a moment ago
                current = store.membership(email)
        if current and current["class_id"] == class_id:
            result["already_here"].append(email)
        else:
            result["elsewhere"].append({"email": email, "class_name": current["class_name"] if current else ""})
    return result


@router.delete("/{class_id}/students/{email:path}", status_code=204)
def remove_student(class_id: int, email: str, request: Request, user: dict = Depends(teacher_only)) -> None:
    own_class(request, class_id, user)
    if not request.app.state.store.remove_member(class_id, email.strip().lower()):
        raise HTTPException(404, "התלמיד לא נמצא בכיתה")
