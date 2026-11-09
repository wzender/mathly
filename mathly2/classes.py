"""Classes. A manager (or a developer) makes, changes and deletes them; a class's teacher, or a manager, adds and
removes its students; a teacher sees the classes they teach; a manager sees every student."""
from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from . import reads
from .access import allowed, need
from .auth import EMAIL
from .store import ClassExists, MemberExists, TeacherIsStudent

MAX_EMAILS = 200
MAX_NAME = 80
router = APIRouter(prefix="/api/classes")
teaching = APIRouter(prefix="/api")


class ClassBody(BaseModel):
    name: str = Field(max_length=200)
    lessons: list[str] = Field(default_factory=list, max_length=200)   # ignored: kept so older clients still work
    teacher_email: str | None = Field(default=None, max_length=300)
    students: str | None = Field(default=None, max_length=40000)   # pasted text: the whole roster of the class
    ai_enabled: bool = False
    ai_daily_checks: int = 150


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


def shown(request: Request, row: dict, with_students: bool = True) -> dict:
    out = {k: row[k] for k in ("id", "name", "lessons", "teacher_email", "ai_enabled", "ai_daily_checks", "students")}
    if with_students:
        out["student_emails"] = [m["email"] for m in request.app.state.store.members(row["id"])]
    return out


def checked(request: Request, body: ClassBody) -> dict:
    """The class fields from a request, or an HTTP error that says what is wrong."""
    name = " ".join(body.name.split())
    if not 1 <= len(name) <= MAX_NAME:
        raise HTTPException(422, f"שם הכיתה צריך להיות בין תו אחד ל־{MAX_NAME} תווים")
    lessons = [lesson["id"] for lesson in request.app.state.bank.lessons]      # every class studies the whole course
    teacher = (body.teacher_email or "").strip().lower() or None
    if teacher and not EMAIL.match(teacher):
        raise HTTPException(422, "כתובת המורה לא נראית כמו מייל")
    if not 0 <= body.ai_daily_checks <= 10000:
        raise HTTPException(422, "מספר בדיקות ה־AI ביום צריך להיות בין 0 ל־10000")
    roster, invalid = parse_emails(body.students or "")
    if len(roster) > 2 * MAX_EMAILS:
        raise HTTPException(422, "יותר מדי תלמידים בבת אחת")
    if teacher and teacher in roster:
        raise HTTPException(422, "מורה הכיתה לא יכול להיות גם תלמיד בה")
    return {"name": name, "lessons": lessons, "teacher_email": teacher, "ai_enabled": body.ai_enabled,
            "ai_daily_checks": body.ai_daily_checks, "roster": roster, "invalid": invalid}


def sync_roster(store, class_id: int, roster: list[str]) -> None:
    """Make the class's students exactly `roster`. Removing a student never deletes their progress."""
    current = {m["email"] for m in store.members(class_id)}
    for email in roster:
        if email not in current:
            store.add_member(class_id, email)
    for email in current - set(roster):
        store.remove_member(class_id, email)


def own_class_for_roster(request: Request, class_id: int, user: dict) -> dict:
    """A manager (or developer) reaches any class; a teacher only the classes they teach."""
    row = request.app.state.store.get_class(class_id)
    if not row:
        raise HTTPException(404, "הכיתה לא נמצאה")
    if not allowed(user["roles"], "classes.manage") and row["teacher_email"] != user["email"]:
        raise HTTPException(404, "הכיתה לא נמצאה")
    return row


# ---- the manager ----

@router.get("")
def list_classes(request: Request, user: dict = Depends(need("classes.manage"))) -> list[dict]:
    return [shown(request, c) for c in request.app.state.store.classes()]


@router.post("", status_code=201)
def create_class(body: ClassBody, request: Request, user: dict = Depends(need("classes.manage"))) -> dict:
    fields = checked(request, body)
    store = request.app.state.store
    try:
        row = store.create_class(user["email"], fields["name"], lessons=fields["lessons"], teacher_email=fields["teacher_email"],
                                 ai_enabled=fields["ai_enabled"], ai_daily_checks=fields["ai_daily_checks"])
    except ClassExists:
        raise HTTPException(409, "כבר יש כיתה בשם הזה") from None
    sync_roster(store, row["id"], fields["roster"])
    request.app.state.roles.forget()
    return {**shown(request, store.get_class(row["id"])), "invalid": fields["invalid"]}


@router.put("/{class_id}")
def change_class(class_id: int, body: ClassBody, request: Request, user: dict = Depends(need("classes.manage"))) -> dict:
    fields = checked(request, body)
    store = request.app.state.store
    try:
        store.update_class(class_id, name=fields["name"], lessons=fields["lessons"], teacher_email=fields["teacher_email"],
                           ai_enabled=fields["ai_enabled"], ai_daily_checks=fields["ai_daily_checks"])
    except KeyError:
        raise HTTPException(404, "הכיתה לא נמצאה") from None
    except ClassExists:
        raise HTTPException(409, "כבר יש כיתה בשם הזה") from None
    except TeacherIsStudent:
        raise HTTPException(422, "מורה הכיתה לא יכול להיות גם תלמיד בה") from None
    if body.students is not None:
        sync_roster(store, class_id, fields["roster"])
    request.app.state.roles.forget()
    return {**shown(request, store.get_class(class_id)), "invalid": fields["invalid"]}


@router.delete("/{class_id}", status_code=204)
def delete_class(class_id: int, request: Request, user: dict = Depends(need("classes.manage"))) -> None:
    if not request.app.state.store.delete_class(class_id):
        raise HTTPException(404, "הכיתה לא נמצאה")
    request.app.state.roles.forget()


@router.get("/{class_id}")
def show_class(class_id: int, request: Request, user: dict = Depends(need("classes.manage"))) -> dict:
    row = request.app.state.store.get_class(class_id)
    if not row:
        raise HTTPException(404, "הכיתה לא נמצאה")
    return shown(request, row)


# ---- the roster: the class's teacher, or a manager ----

@router.post("/{class_id}/students")
def add_students(class_id: int, body: NewStudents, request: Request, user: dict = Depends(need("class.roster"))) -> dict:
    row = own_class_for_roster(request, class_id, user)
    store = request.app.state.store
    valid, invalid = parse_emails(body.emails)
    if len(valid) > MAX_EMAILS:
        raise HTTPException(422, f"אפשר להוסיף עד {MAX_EMAILS} תלמידים בכל פעם")
    result: dict = {"added": [], "already_here": [], "teacher": [], "invalid": invalid}
    for email in valid:
        try:
            store.add_member(row["id"], email)
            result["added"].append(email)
        except MemberExists:
            result["already_here"].append(email)
        except TeacherIsStudent:
            result["teacher"].append(email)
    request.app.state.roles.forget()
    return result


@router.delete("/{class_id}/students/{email:path}", status_code=204)
def remove_student(class_id: int, email: str, request: Request, user: dict = Depends(need("class.roster"))) -> None:
    own_class_for_roster(request, class_id, user)
    if not request.app.state.store.remove_member(class_id, email.strip().lower()):
        raise HTTPException(404, "התלמיד לא נמצא בכיתה")
    request.app.state.roles.forget(email)


# ---- the teacher's and the manager's lists ----

@teaching.get("/teaching")
def my_classes(request: Request, user: dict = Depends(need("class.teach"))) -> list[dict]:
    """The classes I teach, each with its students. A developer sees every class."""
    store = request.app.state.store
    rows = store.classes() if allowed(user["roles"], "*") else store.classes_taught(user["email"])
    return [{"id": c["id"], "name": c["name"], "lessons": c["lessons"], "ai_enabled": c["ai_enabled"],
             "students": [{"email": m["email"], "signed_in": bool(m["user_id"])} for m in store.members(c["id"])]} for c in rows]


@teaching.get("/students")
def all_students(request: Request, user: dict = Depends(need("students.list"))) -> list[dict]:
    return request.app.state.store.all_students()


# ---- the curriculum: the date by which each lesson should be completed (one for the whole school) ----

curriculum = APIRouter(prefix="/api/curriculum")


class Dates(BaseModel):
    dates: dict[str, str | None] = Field(max_length=200)        # lesson id -> "YYYY-MM-DD", or null to clear


@curriculum.get("")
def read_curriculum(request: Request, user: dict = Depends(need("classes.manage"))) -> list[dict]:
    """Every lesson in the bank's order with its date (or null) and the bank's month as a hint."""
    dates = reads.of(request).curriculum()
    return [{"id": lesson["id"], "name": lesson["name"], "month": lesson.get("when", ""), "due_date": dates[lesson["id"]].isoformat() if lesson["id"] in dates else None}
            for lesson in request.app.state.bank.lessons]


@curriculum.put("")
def change_curriculum(body: Dates, request: Request, user: dict = Depends(need("classes.manage"))) -> list[dict]:
    known = {lesson["id"] for lesson in request.app.state.bank.lessons}
    parsed: dict[str, date | None] = {}
    for lesson, text in body.dates.items():
        if lesson not in known:
            raise HTTPException(422, "שיעור לא מוכר")
        try:
            parsed[lesson] = date.fromisoformat(text) if text else None
        except ValueError:
            raise HTTPException(422, "תאריך לא תקין") from None
    request.app.state.store.set_lesson_dates(parsed)
    request.state.reads = None                                     # what this request read is out of date now
    return read_curriculum(request, user)
