"""Assignments: a teacher gives work to a class (pages from a file, a photo or the board; one of the bank's written quizzes; or an exercise test
of a real test), students hand in pictures, the teacher checks them from one inbox."""
from __future__ import annotations

from datetime import date as Day
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from . import attempts, cleanup, clock, pictures, reads
from .access import allowed, learner, need
from .pictures import PictureError
from .realtests import _my_class, lesson_names
from .written import picture_error

router = APIRouter(prefix="/api")
MAX_PAGES = 20


class NewAssignment(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=1000)
    due_date: Day
    kind: Literal["pages", "quiz", "exercise_test"]
    pages: list[str] = Field(default_factory=list, max_length=MAX_PAGES)
    quiz_lesson: str | None = None
    test_id: int | None = None
    exercise_number: Literal[1, 2] | None = None


def written_quiz(bank, lesson_id: str) -> dict | None:
    """The authored written quiz of a lesson (minutes and questions with points), or None."""
    unit = next((u for u in bank.data["units"] if u["id"] == lesson_id), None)
    return (unit or {}).get("quiz") or None


def quiz_view(bank, lesson_id: str) -> dict | None:
    quiz = written_quiz(bank, lesson_id)
    if not quiz:
        return None
    return {"minutes": quiz["minutes"], "points": sum(q["points"] for q in quiz["questions"]),
            "questions": [{k: q[k] for k in ("question", "points", "figure", "graph") if k in q} for q in quiz["questions"]]}


# ---- the teacher: pages, giving, listing, removing ----

@router.post("/assignments/pages", status_code=201)
async def upload_pages(request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    """One file of an assignment: an image (one page) or a PDF (a page per sheet). Returns the page pictures' ids, in order."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > pictures.MAX_PDF + 1024:
        raise picture_error(PictureError(413, "pdf_too_large"))
    data = await request.body()
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()

    def work() -> list[str]:
        sheets = pictures.render_pdf(data) if kind == "application/pdf" else [pictures.clean_image(data, kind)]
        made = [pictures.store_picture(request.app.state.store, request.app.state.pictures, user["id"], "page", jpeg) for jpeg in sheets]
        return [row["id"] for row in made]
    try:
        ids = await run_in_threadpool(work)
    except PictureError as exc:
        raise picture_error(exc) from exc
    return {"pictures": ids}


def _checked_pages(request: Request, user: dict, ids: list[str]) -> list[str]:
    store = request.app.state.store
    found = list(dict.fromkeys(ids))
    for pid in found:
        pic = store.get_picture(pid)
        if pic is None or pic["kind"] != "page" or pic["owner_id"] != user["id"] or pic["deleted_at"]:
            raise HTTPException(422, "אחד העמודים לא תקין")
    return found


@router.post("/classes/{class_id}/assignments", status_code=201)
def give_assignment(class_id: int, body: NewAssignment, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    klass = _my_class(request, user, class_id)
    store, bank, today = request.app.state.store, request.app.state.bank, clock.school_day()
    if body.due_date < today:
        raise HTTPException(422, "תאריך ההגשה כבר עבר")
    fields: dict = {}
    if body.kind == "pages":
        fields["pages"] = _checked_pages(request, user, body.pages)
        if not fields["pages"]:
            raise HTTPException(422, "צריך לפחות עמוד אחד")
    elif body.kind == "quiz":
        if body.quiz_lesson not in klass["lessons"] or not written_quiz(bank, body.quiz_lesson):
            raise HTTPException(422, "לשיעור הזה אין בוחן כתוב, או שהוא לא של הכיתה")
        fields["quiz_lesson"] = body.quiz_lesson
    else:
        test = store.get_test(body.test_id) if body.test_id is not None else None
        if test is None or test["removed_at"] or test["class_id"] != class_id or body.exercise_number is None:
            raise HTTPException(422, "המבחן לא נמצא בכיתה הזו")
        fields.update(test_id=body.test_id, exercise_number=body.exercise_number)
    row = store.create_assignment(class_id, body.title.strip(), body.due_date, user["email"], body.kind, note=body.note.strip(),
                                  created_at=clock.now(), **fields)
    return teacher_assignment(request, row, klass, [], today)


def teacher_assignment(request: Request, row: dict, klass: dict, subs: list[dict], today: Day) -> dict:
    """An assignment as its teacher sees it, with how many students handed in, were checked, were sent back, and (for an exercise test) did it."""
    store, here = request.app.state.store, reads.of(request)
    members = store.members(klass["id"])
    out = {"id": row["id"], "class": {"id": klass["id"], "name": klass["name"]}, "title": row["title"], "note": row["note"], "kind": row["kind"],
           "due_date": row["due_date"].isoformat(), "days_left": (row["due_date"] - today).days, "students": len(members), "pages": row["pages"]}
    if row["kind"] == "quiz":
        out["quiz_lesson"] = {"id": row["quiz_lesson"], "name": (lesson_names(request, [row["quiz_lesson"]]) or [""])[0]}
    if row["kind"] == "exercise_test":
        test = store.get_test(row["test_id"])
        out["test"] = {"id": row["test_id"], "number": row["exercise_number"], "date": test["date"].isoformat() if test else None}
        scope = f'{row["test_id"]}:{row["exercise_number"]}'
        ids = [m["user_id"] for m in members if m["user_id"]]
        here.prefetch(*[("attempts_of", uid, "exercise_test") for uid in ids])
        out["done"] = sum(1 for uid in ids if any(r["scope"] == scope and not attempts.is_open(r) for r in here.attempts_of(uid, "exercise_test")))
    else:
        out.update(handed_in=sum(1 for s in subs if s["state"] == "handed_in"), graded=sum(1 for s in subs if s["state"] == "graded"),
                   returned=sum(1 for s in subs if s["state"] == "returned"))
        out["waiting"] = out["handed_in"]
    return out


@router.get("/teaching/assignments")
def teaching_assignments(request: Request, user: dict = Depends(need("class.teach"))) -> list[dict]:
    """The assignments of the classes I teach (a developer: every class), with the counts."""
    store, today = request.app.state.store, clock.school_day()
    classes = store.classes() if allowed(user["roles"], "*") else store.classes_taught(user["email"])
    result = []
    for klass in classes:
        rows = store.assignments_of_classes([klass["id"]])
        subs = store.submissions_of_assignments([r["id"] for r in rows])
        bank = request.app.state.bank
        result.append({"class": {"id": klass["id"], "name": klass["name"],
                                 "lessons": [{"id": i, "name": n, "has_quiz": bool(written_quiz(bank, i))} for i, n in zip(klass["lessons"], lesson_names(request, klass["lessons"]))],
                                 "tests": [{"id": t["id"], "date": t["date"].isoformat(), "lessons": lesson_names(request, t["lessons"])} for t in store.tests_of_classes([klass["id"]])]},
                       "assignments": [teacher_assignment(request, r, klass, [s for s in subs if s["assignment_id"] == r["id"]], today) for r in rows]})
    return result


@router.delete("/assignments/{assignment_id}", status_code=204)
def remove_assignment(assignment_id: int, request: Request, user: dict = Depends(need("class.teach"))) -> None:
    store = request.app.state.store
    row = store.get_assignment(assignment_id)
    if row is None or row["removed_at"]:
        raise HTTPException(404, "המשימה לא נמצאה")
    _my_class(request, user, row["class_id"])
    store.remove_assignment(assignment_id, clock.now())


# ---- the student: my assignments and handing in ----

MAX_ANSWER_PICTURES = 10
OPEN_STATES = ("not_handed", "returned", "not_done")


def _my_assignment(request: Request, user: dict, assignment_id: int) -> dict:
    """An assignment of one of the student's classes (404 for anything else, and for a removed one)."""
    here = reads.of(request)
    row = here.get_assignment(assignment_id)
    mine = {c["id"] for c in here.classes_of_student(user["email"])}
    if row is None or row["removed_at"] or row["class_id"] not in mine:
        raise HTTPException(404, "המשימה לא נמצאה")
    return row


def _exercise_result(request: Request, user: dict, row: dict) -> tuple[str, int | None]:
    """The state of an exercise-test assignment: done once the student has a submitted attempt at it, and the best grade of those."""
    scope = f'{row["test_id"]}:{row["exercise_number"]}'
    grades = [r["grade"] for r in reads.of(request).attempts_of(user["id"], "exercise_test") if r["scope"] == scope and not attempts.is_open(r)]
    return ("done", max(grades)) if grades else ("not_done", None)


def _student_ai(request: Request, user: dict, row: dict, sub: dict, klass: dict | None) -> dict:
    """What the student can do about an answer: ask for an AI check (class with the AI on, not checked yet) or ask the teacher to look again, and the
    state of their requests about it."""
    from . import ai_help
    store = request.app.state.store
    mine = store.ai_requests(user_id=user["id"], assignment_id=row["id"], kinds=["check", "again"])
    checks, again = [r for r in mine if r["kind"] == "check"], [r for r in mine if r["kind"] == "again"]
    asked_again = any(r["state"] == "waiting" for r in again)
    return {"can_check": bool(klass and klass["ai_enabled"] and sub["state"] == "handed_in" and not any(r["state"] in ai_help.OPEN for r in checks)),
            "can_look_again": (sub["state"] in ("graded", "returned") or any(r["state"] == "done" for r in checks)) and not asked_again,
            "asked_again": asked_again, "checks": [ai_help.view(request, r) for r in reversed(checks)][:3]}


def student_assignment(request: Request, user: dict, row: dict, sub: dict | None, today: Day) -> dict:
    """An assignment as its student sees it: its state, grade and the teacher's note."""
    out = {"id": row["id"], "title": row["title"], "note": row["note"], "kind": row["kind"], "due_date": row["due_date"].isoformat(),
           "days_left": (row["due_date"] - today).days, "grade": None, "teacher_note": "", "late": False}
    klass = reads.of(request).get_class(row["class_id"])
    out["class"] = {"id": row["class_id"], "name": klass["name"] if klass else ""}
    if row["kind"] == "exercise_test":
        out["state"], out["grade"] = _exercise_result(request, user, row)
        out["test"] = {"id": row["test_id"], "number": row["exercise_number"]}
    elif sub is None:
        out["state"] = "not_handed"
    else:
        out.update(state=sub["state"], grade=sub["grade"], teacher_note=sub["teacher_note"], late=sub["late"], handed_at=sub["handed_at"].isoformat())
    out["overdue"] = out["days_left"] < 0 and out["state"] in OPEN_STATES
    if row["kind"] != "exercise_test" and sub is not None:
        out["ai"] = _student_ai(request, user, row, sub, klass)
    return out


@router.get("/assignments")
def my_assignments(request: Request, user: dict = Depends(learner)) -> list[dict]:
    """The student's assignments: the open ones first by due date, then the done ones."""
    here, today = reads.of(request), clock.school_day()
    class_ids = [c["id"] for c in here.classes_of_student(user["email"])]
    here.prefetch(("assignments_of_classes", class_ids), ("submissions_of_user", user["id"]), ("attempts_of", user["id"], "exercise_test"))
    subs = {s["assignment_id"]: s for s in here.submissions_of_user(user["id"])}
    shown = [student_assignment(request, user, r, subs.get(r["id"]), today) for r in here.assignments_of_classes(class_ids)]
    return sorted(shown, key=lambda a: (a["state"] not in OPEN_STATES, a["due_date"], a["id"]))


@router.get("/assignments/{assignment_id}")
def my_assignment(assignment_id: int, request: Request, user: dict = Depends(learner)) -> dict:
    row = _my_assignment(request, user, assignment_id)
    here, bank, today = reads.of(request), request.app.state.bank, clock.school_day()
    sub = here.get_submission(assignment_id, user["id"])
    out = student_assignment(request, user, row, sub, today)
    out["pages"] = row["pages"]
    if row["kind"] == "quiz":
        out["quiz"] = quiz_view(bank, row["quiz_lesson"])
    pics = []
    for pid in (sub["pictures"] if sub else []):
        pic = request.app.state.store.get_picture(pid)
        pics.append({"id": pid, "deleted": bool(pic and pic["deleted_at"])})
    out["pictures"] = pics
    return out


class Handing(BaseModel):
    pictures: list[str] = Field(min_length=1, max_length=MAX_ANSWER_PICTURES)


@router.post("/assignments/{assignment_id}/submission")
def hand_in(assignment_id: int, body: Handing, request: Request, user: dict = Depends(learner)) -> dict:
    """Hand in (or replace, or hand in again after a return) the student's picture answers. A graded submission cannot be changed."""
    store, today = request.app.state.store, clock.school_day()
    row = _my_assignment(request, user, assignment_id)
    if row["kind"] == "exercise_test":
        raise HTTPException(422, "מבחן תרגול לא מגישים בתמונה: עושים אותו באפליקציה")
    existing = store.get_submission(assignment_id, user["id"])
    if existing and existing["state"] == "graded":
        raise HTTPException(409, "המשימה כבר נבדקה ולא אפשר לשנות אותה")
    ids = list(dict.fromkeys(body.pictures))
    for pid in ids:
        pic = store.get_picture(pid)
        if pic is None or pic["kind"] != "answer" or pic["owner_id"] != user["id"] or pic["deleted_at"]:
            raise HTTPException(422, "אחת התמונות לא תקינה")
    saved = store.save_submission(assignment_id, user["id"], pictures=ids, state="handed_in", late=today > row["due_date"], handed_at=clock.now(),
                                  grade=None, teacher_note="" if not existing else existing["teacher_note"], checked_at=None, checked_by=None)
    return student_assignment(request, user, row, saved, today)


# ---- the teacher: the inbox and checking ----

class Check(BaseModel):
    grade: int = Field(ge=0, le=100)
    note: str = Field(default="", max_length=2000)
    seen: str                                   # the handed_at the teacher was looking at


class SendBack(BaseModel):
    note: str = Field(min_length=1, max_length=2000)
    seen: str


def _teachable_classes(request: Request, user: dict) -> list[dict]:
    store = request.app.state.store
    return store.classes() if allowed(user["roles"], "*") else store.classes_taught(user["email"])


def _student_emails(request: Request, class_id: int) -> dict[str, str]:
    return {m["user_id"]: m["email"] for m in request.app.state.store.members(class_id) if m["user_id"]}


def inbox_item(request: Request, sub: dict, assignment: dict, klass: dict, emails: dict[str, str]) -> dict:
    return {"kind": "submission", "id": sub["id"], "assignment": {"id": assignment["id"], "title": assignment["title"], "kind": assignment["kind"],
                                                                  "class": {"id": klass["id"], "name": klass["name"]}},
            "student": emails.get(sub["user_id"], ""), "handed_at": sub["handed_at"].isoformat(), "late": sub["late"], "seen": sub["handed_at"].isoformat(),
            "pictures": [{"id": p} for p in sub["pictures"]]}


@router.get("/teaching/inbox")
def inbox(request: Request, user: dict = Depends(need("class.teach"))) -> list[dict]:
    """Everything the teacher's students handed in that waits for them, oldest first. A submission sent back waits for the student and is not here."""
    store, items = request.app.state.store, []
    for klass in _teachable_classes(request, user):
        rows = {r["id"]: r for r in store.assignments_of_classes([klass["id"]]) if r["kind"] != "exercise_test"}
        emails = _student_emails(request, klass["id"])
        subs = store.submissions_of_assignments(list(rows))
        items += [inbox_item(request, s, rows[s["assignment_id"]], klass, emails) for s in subs if s["state"] == "handed_in"]
        again = {(r["assignment_id"], r["user_id"]): r for r in store.ai_requests(class_ids=[klass["id"]], kinds=["again"], states=["waiting"])}
        for s in subs:                                                  # a student asked to look again at a checked answer
            asked = again.get((s["assignment_id"], s["user_id"]))
            if asked and s["state"] != "handed_in":
                items.append({**inbox_item(request, s, rows[s["assignment_id"]], klass, emails), "kind": "again", "asked_at": asked["created_at"].isoformat(),
                              "handed_at": asked["created_at"].isoformat(), "seen": s["handed_at"].isoformat()})
    return sorted(items, key=lambda i: (i["handed_at"], i["id"]))


def _my_submission(request: Request, user: dict, submission_id: int) -> tuple[dict, dict, dict]:
    store = request.app.state.store
    sub = store.get_submission_by_id(submission_id)
    row = store.get_assignment(sub["assignment_id"]) if sub else None
    if sub is None or row is None or row["removed_at"]:
        raise HTTPException(404, "ההגשה לא נמצאה")
    return sub, row, _my_class(request, user, row["class_id"])


@router.get("/submissions/{submission_id}")
def open_submission(submission_id: int, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    sub, row, klass = _my_submission(request, user, submission_id)
    out = inbox_item(request, sub, row, klass, _student_emails(request, klass["id"]))
    out.update(state=sub["state"], grade=sub["grade"], teacher_note=sub["teacher_note"], pages=row["pages"], note=row["note"],
               quiz=quiz_view(request.app.state.bank, row["quiz_lesson"]) if row["kind"] == "quiz" else None)
    out["pictures"] = [{"id": p, "deleted": bool((request.app.state.store.get_picture(p) or {}).get("deleted_at"))} for p in sub["pictures"]]
    from . import ai_help
    store = request.app.state.store
    check = ai_help.latest_check(store, sub["assignment_id"], sub["user_id"])
    out["ai"] = ai_help.view(request, check, staff=True) if check else None                        # a suggestion: the teacher's grade wins
    checks = store.ai_requests(user_id=sub["user_id"], assignment_id=sub["assignment_id"], kinds=["check"])
    newest = checks[-1] if checks else None
    out["ai_open"] = bool(newest and newest["state"] in ai_help.OPEN)
    out["ai_failed"] = ai_help.view(request, newest, staff=True) if newest and newest["state"] == "failed" else None
    out["ai_enabled"] = bool(klass["ai_enabled"])
    out["look_again"] = bool(store.ai_requests(user_id=sub["user_id"], assignment_id=sub["assignment_id"], kinds=["again"], states=["waiting"]))
    return out


def _check(request: Request, user: dict, submission_id: int, seen: str) -> tuple[dict, dict]:
    sub, row, _ = _my_submission(request, user, submission_id)
    try:
        saw = datetime.fromisoformat(seen)
    except ValueError:
        raise HTTPException(422, "seen לא תקין") from None
    again = bool(request.app.state.store.ai_requests(user_id=sub["user_id"], assignment_id=sub["assignment_id"], kinds=["again"], states=["waiting"]))
    if sub["state"] != "handed_in" and not again:
        raise HTTPException(409, "ההגשה כבר נבדקה או הוחזרה")
    if saw != sub["handed_at"]:
        raise HTTPException(409, "ההגשה השתנתה. פתחו אותה שוב.")
    return sub, row


@router.post("/submissions/{submission_id}/grade")
def grade_submission(submission_id: int, body: Check, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    from . import ai_help
    sub, _ = _check(request, user, submission_id, body.seen)
    saved = request.app.state.store.save_submission(sub["assignment_id"], sub["user_id"], state="graded", grade=body.grade, teacher_note=body.note.strip(),
                                                    checked_at=clock.now(), checked_by=user["email"])
    ai_help.close_look_again(request.app.state.store, sub["assignment_id"], sub["user_id"])      # saving a review closes the student's request
    return {"id": saved["id"], "state": saved["state"], "grade": saved["grade"]}


@router.post("/submissions/{submission_id}/return")
def return_submission(submission_id: int, body: SendBack, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    from . import ai_help
    sub, _ = _check(request, user, submission_id, body.seen)
    if not body.note.strip():
        raise HTTPException(422, "צריך לכתוב מה לתקן")
    saved = request.app.state.store.save_submission(sub["assignment_id"], sub["user_id"], state="returned", grade=None, teacher_note=body.note.strip(),
                                                    checked_at=clock.now(), checked_by=user["email"])
    ai_help.close_look_again(request.app.state.store, sub["assignment_id"], sub["user_id"])
    return {"id": saved["id"], "state": saved["state"]}


# ---- the grades screen's rows ----

def grade_rows(request: Request, user: dict) -> list[dict]:
    """Graded assignments and done exercise-test assignments, with the teacher's note. A removed assignment keeps its grade."""
    store, here = request.app.state.store, reads.of(request)
    class_ids = [c["id"] for c in here.classes_of_student(user["email"])]
    rows = {r["id"]: r for r in store.assignments_of_classes(class_ids, include_removed=True)}
    out = []
    subs = {s["assignment_id"]: s for s in store.submissions_of_user(user["id"])}
    here.prefetch(("attempts_of", user["id"], "exercise_test"))
    for row in rows.values():
        item = {"assignment": {"id": row["id"], "title": row["title"], "kind": row["kind"], "due_date": row["due_date"].isoformat(), "removed": bool(row["removed_at"])}}
        if row["kind"] == "exercise_test":
            state, grade = _exercise_result(request, user, row)
            if state == "done":
                out.append({**item, "grade": grade, "note": ""})
        elif row["id"] in subs and subs[row["id"]]["state"] == "graded":
            out.append({**item, "grade": subs[row["id"]]["grade"], "note": subs[row["id"]]["teacher_note"]})
    return sorted(out, key=lambda r: (r["assignment"]["due_date"], r["assignment"]["id"]))


# ---- deleting a student's pictures on request ----

@router.delete("/classes/{class_id}/pictures/{email:path}")
def delete_student_pictures(class_id: int, email: str, request: Request, user: dict = Depends(need("class.roster"))) -> dict:
    """Delete a student's answer pictures for this class's assignments now. The class's teacher, a manager or a developer may. The submissions
    keep their grade and note."""
    store = request.app.state.store
    klass = store.get_class(class_id)
    is_teacher = klass is not None and (klass["teacher_email"] or "").lower() == user["email"]
    if klass is None or not (is_teacher or allowed(user["roles"], "classes.manage") or allowed(user["roles"], "*")):
        raise HTTPException(404, "הכיתה לא נמצאה")
    member = next((m for m in store.members(class_id) if m["email"] == email.strip().lower()), None)
    if member is None:
        raise HTTPException(404, "התלמיד לא נמצא בכיתה")
    if not member["user_id"]:
        return {"deleted": 0}                                                    # never signed in: nothing was handed in
    ids = [a["id"] for a in store.assignments_of_classes([class_id], include_removed=True)]
    return {"deleted": cleanup.delete_answer_pictures(store, request.app.state.pictures, ids, member["user_id"], clock.now())}


# ---- the numbers on the teacher's tabs ----

@router.get("/teaching/counts")
def teaching_counts(request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    """How many items each tab of the teacher's screen holds: the classes they teach, their tests, their assignments, and the submissions waiting."""
    store = request.app.state.store
    classes = _teachable_classes(request, user)
    ids = [c["id"] for c in classes]
    here = reads.of(request)
    here.prefetch(("tests_of_classes", ids), ("assignments_of_classes", ids))
    tests, assignments = here.tests_of_classes(ids), here.assignments_of_classes(ids)
    graded_by_student = [a["id"] for a in assignments if a["kind"] != "exercise_test"]
    waiting = sum(1 for s in store.submissions_of_assignments(graded_by_student) if s["state"] == "handed_in")
    here.prefetch(*[("members", i) for i in ids])
    students = len({m["email"] for i in ids for m in here.members(i)})
    ai_waiting = len(store.ai_requests(class_ids=ids, kinds=["photo", "check"], states=["waiting"])) if ids else 0
    again = len(store.ai_requests(class_ids=ids, kinds=["again"], states=["waiting"])) if ids else 0          # students asking to look again are in the inbox
    return {"classes": len(classes), "tests": len(tests), "assignments": len(assignments), "inbox": waiting + again, "progress": students, "ai": ai_waiting}
