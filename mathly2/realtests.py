"""Real tests: a teacher sets one for a class; every student of the class gets a countdown, two exercise tests, one simulation and a
readiness number from it. Nothing is created per student: it is all derived from the test, the student's skill states and their attempts."""
from __future__ import annotations

from datetime import date, timedelta
from datetime import date as Day

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import attempts, clock, countdown, exam, readiness, reads
from .access import allowed, learner, need
from .learning import MASTERED, next_skill, skill_state

router = APIRouter(prefix="/api")

LESSON_FIELDS = ("date", "lessons", "note", "questions", "minutes")


class TestBody(BaseModel):
    date: Day
    subject_id: str | None = Field(default=None, max_length=40)   # None: the subject of the chosen lessons
    lessons: list[str] = Field(min_length=1, max_length=200)
    note: str = Field(default="", max_length=500)
    questions: int = Field(default=12, ge=1, le=40)
    minutes: int = Field(default=45, ge=5, le=180)


class TestChange(BaseModel):
    date: Day | None = None
    lessons: list[str] | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=500)
    questions: int | None = Field(default=None, ge=1, le=40)
    minutes: int | None = Field(default=None, ge=5, le=180)


# ---- what a test knows about one student ----

def lesson_names(request: Request, ids: list[str]) -> list[str]:
    names = {l["id"]: l["name"] for l in request.app.state.bank.lessons}
    return [names.get(i, i) for i in ids]


def _covered(bank, test: dict) -> list[str]:
    """The skills the test covers that have questions, in the bank's order."""
    return [s["id"] for s in bank.skills if s["unit"] in test["lessons"] and bank.question_keys(s["id"])]


def prime_students(request: Request, user_ids: list[str], kinds: tuple[str, ...] = ("exercise_test", "simulation")) -> None:
    """Read what a class's students need (progress, last answers and attempts of each kind) with one call each for all of them, together,
    and hand it to the request's reads, so asking for one student's later does not touch the database."""
    ids = list(dict.fromkeys(user_ids))
    if not ids:
        return
    store, here = request.app.state.store, reads.of(request)
    jobs = {"progress_of": reads.POOL.submit(store.progress_of_users, ids), "last_answered": reads.POOL.submit(store.last_answered_users, ids)}
    jobs.update({("attempts_of", kind): reads.POOL.submit(store.attempts_of_users, ids, kind) for kind in kinds})
    for key, future in jobs.items():
        found = future.result()
        for uid in ids:
            if isinstance(key, tuple):
                here.prime(key[0], (uid, key[1]), found[uid])
            else:
                here.prime(key, (uid,), found[uid])


def _student_reads(user_id: str) -> list[tuple]:
    return [("progress_of", user_id), ("last_answered", user_id), ("attempts_of", user_id, "exercise_test"), ("attempts_of", user_id, "simulation")]


def facts_for(request: Request, user_id: str | None, test: dict, today: date) -> dict:
    """Everything the plan, the readiness meter and the draws need about one student and one test."""
    store, bank, now, here = request.app.state.store, request.app.state.bank, clock.now(), reads.of(request)
    covered = _covered(bank, test)
    if user_id:
        here.prefetch(*_student_reads(user_id))                      # the four reads together (done once per request: a second test reuses them)
    states = {p["skill_id"]: skill_state(p) for p in here.progress_of(user_id)} if user_id else {}
    last = here.last_answered(user_id) if user_id else {}
    tid = str(test["id"])

    def mine(kind: str) -> list[dict]:
        rows = here.attempts_of(user_id, kind) if user_id else []
        return [attempts.settle(store, bank, r, now) for r in rows if r["scope"] == tid or r["scope"].startswith(tid + ":")]

    exercise = {1: [], 2: []}
    for row in mine("exercise_test"):
        exercise[int(row["scope"].split(":")[1])].append(row)
    simulation = next(iter(mine("simulation")), None)
    submitted = lambda rows: [r for r in rows if not attempts.is_open(r)]
    best = {n: max((r["grade"] for r in submitted(rows)), default=None) for n, rows in exercise.items()}
    weak_before = {s["id"] for rows in exercise.values() for r in submitted(rows) for s in attempts.result(bank, r)["lost_skills"]}
    failed: list[str] = []
    review_left: list[str] = []
    if simulation and not attempts.is_open(simulation):
        failed = [s["id"] for s in attempts.result(bank, simulation)["lost_skills"]]
        sim_day = clock.school_day(simulation["submitted_at"])
        review_left = [i for i in failed if last.get(i) is None or last[i] <= sim_day]       # not practised after the simulation
    mastered = [i for i in covered if states.get(i) == MASTERED]
    unmastered = [i for i in covered if states.get(i) != MASTERED]
    sim_taken = bool(simulation and not attempts.is_open(simulation))
    stale = sorted(covered, key=lambda i: (last.get(i) is not None, last.get(i) or date.min))
    used: dict[str, int] = {}
    for rows in list(exercise.values()) + [[simulation] if simulation else []]:
        for r in rows:
            for q in r["questions"]:
                used[q["key"]] = used.get(q["key"], 0) + 1
    return {"covered": covered, "states": states, "mastered": len(mastered), "path_done": bool(covered) and not unmastered,
            "next_path_skill": unmastered[0] if unmastered else None, "exercise": exercise, "best": best, "simulation": simulation,
            "sim_taken": sim_taken, "ex1_done": bool(submitted(exercise[1])), "ex2_done": bool(submitted(exercise[2])),
            "weak_before": weak_before, "failed": failed, "review_left": review_left, "stale": stale, "used": used}


def readiness_for(facts: dict) -> dict:
    m = readiness.mastery_percent(facts["mastered"], len(facts["covered"]))
    e = readiness.exercise_average([g for g in facts["best"].values() if g is not None])
    s = facts["simulation"]["grade"] if facts["sim_taken"] else None
    return readiness.compute(m, e, s)


def plan_for(test: dict) -> dict:
    return countdown.plan(test["date"], clock.school_day(test["created_at"]))


def card(request: Request, user_id: str | None, test: dict, today: date) -> dict:
    """A test as its student sees it: the plan, readiness, both exercise tests, the simulation, and today's task."""
    bank = request.app.state.bank
    facts = facts_for(request, user_id, test, today)
    p = plan_for(test)
    days_left = (test["date"] - today).days
    exercises = []
    for n in (1, 2):
        rows = facts["exercise"][n]
        open_ = next((r for r in rows if attempts.is_open(r)), None)
        exercises.append({"number": n, "best": facts["best"][n], "attempts": len([r for r in rows if not attempts.is_open(r)]),
                          "open": bool(open_), "due_at": open_["due_at"].isoformat() if open_ and attempts.is_timed(open_) else None})
    sim = facts["simulation"]
    opens_in = max(0, days_left - p["sim"])
    return {"id": test["id"], "date": test["date"].isoformat(), "days_left": days_left, "note": test["note"], "subject_id": test.get("subject_id", "math"),
            "lessons": [{"id": i, "name": n} for i, n in zip(test["lessons"], lesson_names(request, test["lessons"]))],
            "questions": test["questions"], "minutes": test["minutes"],
            "plan": countdown.outline(p, facts), "task": countdown.task(days_left, p, facts), "readiness": readiness_for(facts),
            "exercise_tests": exercises,
            "practice_first": [{"id": i, "name": bank.skill(i)["name"]} for i in facts["covered"] if facts["states"].get(i, "not_started") == "not_started"],
            "simulation": {"open_now": countdown.sim_open(days_left, p), "opens_in_days": opens_in,
                           "opens_on": (test["date"] - timedelta(days=p["sim"])).isoformat(), "required": countdown.sim_open(days_left, p) and not facts["sim_taken"],
                           "taken": facts["sim_taken"], "grade": sim["grade"] if facts["sim_taken"] else None,
                           "attempt": sim["id"] if sim else None, "in_progress": bool(sim and attempts.is_open(sim)),
                           "review": [{"id": i, "name": bank.skill(i)["name"]} for i in facts["failed"] if bank.skill(i)]}}


# ---- the teacher: set, change, remove, and see who took the simulation ----

def _my_class(request: Request, user: dict, class_id: int) -> dict:
    row = request.app.state.store.get_class(class_id)
    if row is None or not (allowed(user["roles"], "*") or (row["teacher_email"] or "").lower() == user["email"]):
        raise HTTPException(404, "הכיתה לא נמצאה")
    return row


def _my_test(request: Request, user: dict, test_id: int) -> tuple[dict, dict]:
    test = request.app.state.store.get_test(test_id)
    if test is None or test["removed_at"]:
        raise HTTPException(404, "המבחן לא נמצא")
    return test, _my_class(request, user, test["class_id"])


def class_lessons(request: Request, klass: dict) -> list[dict]:
    """The lessons a class studies: every lesson of its subjects, in the bank's order."""
    subjects = klass.get("subjects") or ["math"]
    return [l for l in request.app.state.bank.lessons if l.get("subject_id", "math") in subjects]


def _checked_lessons(request: Request, klass: dict, lessons: list[str], subject: str | None = None) -> tuple[list[str], str]:
    """(the lessons, their one subject). A test covers lessons the class studies, all of one subject."""
    bank, ids = request.app.state.bank, list(dict.fromkeys(lessons))
    studied = {l["id"] for l in class_lessons(request, klass)}
    if not ids or any(i not in studied for i in ids):
        raise HTTPException(422, "אפשר לבחור רק שיעורים של הכיתה")
    subjects = {bank.subject_of_lesson(i) for i in ids}
    if len(subjects) > 1 or (subject is not None and subjects != {subject}):
        raise HTTPException(422, "מבחן מכסה שיעורים של מקצוע אחד בלבד")
    return ids, subjects.pop()


def teacher_view(request: Request, test: dict, klass: dict, today: date) -> dict:
    store, here = request.app.state.store, reads.of(request)
    members = store.members(klass["id"])
    prime_students(request, [m["user_id"] for m in members if m["user_id"]])                                  # every student's reads at once
    students = []
    for m in members:
        facts = facts_for(request, m["user_id"], test, today)
        students.append({"email": m["email"], "signed_in": bool(m["user_id"]), "simulation_taken": facts["sim_taken"],
                         "readiness": readiness_for(facts)})
    taken = sum(1 for s in students if s["simulation_taken"])
    return {"id": test["id"], "class": {"id": klass["id"], "name": klass["name"]}, "date": test["date"].isoformat(), "note": test["note"],
            "subject_id": test.get("subject_id", "math"),
            "days_left": (test["date"] - today).days, "questions": test["questions"], "minutes": test["minutes"],
            "lessons": [{"id": i, "name": n} for i, n in zip(test["lessons"], lesson_names(request, test["lessons"]))],
            "simulation": {"taken": taken, "total": len(students), "missing": [s["email"] for s in students if not s["simulation_taken"]]},
            "students": students}


@router.get("/teaching/tests")
def teaching_tests(request: Request, user: dict = Depends(need("class.teach"))) -> list[dict]:
    """The tests of the classes I teach (a developer sees every class), each with who took the simulation."""
    store, today = request.app.state.store, clock.school_day()
    classes = store.classes() if allowed(user["roles"], "*") else store.classes_taught(user["email"])
    by_id = {c["id"]: c for c in classes}
    subjects = {s["id"]: s for s in request.app.state.bank.subjects}
    def offer(c: dict) -> dict:
        lessons = class_lessons(request, c)
        return {"id": c["id"], "name": c["name"], "lessons": [{"id": l["id"], "name": l["name"], "subject_id": l.get("subject_id", "math")} for l in lessons],
                "subjects": [{"id": s, "name": subjects[s]["name"]} for s in (c.get("subjects") or ["math"]) if s in subjects]}
    return [{"class": offer(c),
             "tests": [teacher_view(request, t, c, today) for t in store.tests_of_classes([c["id"]])]} for c in by_id.values()]


@router.post("/classes/{class_id}/tests", status_code=201)
def set_test(class_id: int, body: TestBody, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    klass = _my_class(request, user, class_id)
    today = clock.school_day()
    if body.date < today:
        raise HTTPException(422, "תאריך המבחן כבר עבר")
    lessons, subject = _checked_lessons(request, klass, body.lessons, body.subject_id)
    test = request.app.state.store.create_test(class_id, body.date, lessons, user["email"], note=body.note.strip(), questions=body.questions,
                                                 minutes=body.minutes, created_at=clock.now(), subject_id=subject)
    return teacher_view(request, test, klass, today)


@router.put("/tests/{test_id}")
def change_test(test_id: int, body: TestChange, request: Request, user: dict = Depends(need("class.teach"))) -> dict:
    test, klass = _my_test(request, user, test_id)
    today = clock.school_day()
    if today >= test["date"]:
        raise HTTPException(409, "אי אפשר לשנות מבחן ביום המבחן או אחריו")
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if "date" in fields and fields["date"] < today:
        raise HTTPException(422, "תאריך המבחן כבר עבר")
    if "lessons" in fields:
        fields["lessons"], _ = _checked_lessons(request, klass, fields["lessons"], test.get("subject_id", "math"))
    if "note" in fields:
        fields["note"] = fields["note"].strip()
    updated = request.app.state.store.update_test(test_id, **fields) if fields else test
    return teacher_view(request, updated, klass, today)


@router.delete("/tests/{test_id}", status_code=204)
def remove_test(test_id: int, request: Request, user: dict = Depends(need("class.teach"))) -> None:
    _my_test(request, user, test_id)
    request.app.state.store.remove_test(test_id, clock.now())


# ---- the student: home and a test's card ----

def _with_skill_name(request: Request, task: dict) -> dict:
    skill = request.app.state.bank.skill(task["skill"]) if task.get("skill") else None
    return {**task, "skill_name": skill["name"] if skill else None}


def _next_path_skill(request: Request, user: dict, subject: str = "math") -> str | None:
    """The suggested next skill of the student's path in this subject (the same rule as the path's owl)."""
    from .skills import RECENT, visible_lesson_ids
    bank, here = request.app.state.bank, reads.of(request)
    shown = visible_lesson_ids(request, user)
    order = [s["id"] for lesson in bank.lessons_with_skills() if (shown is None or lesson["id"] in shown) and lesson["subject_id"] == subject
             for s in lesson["skills"]]
    states = {p["skill_id"]: skill_state(p) for p in here.progress_of(user["id"])}
    return next_skill(order, states, here.recent_skills(user["id"], RECENT))


@router.get("/home")
def home(request: Request, user: dict = Depends(learner), subject: str = Query("math", max_length=40)) -> dict:
    """The student's home: the upcoming tests (nearest first) with their readiness, today's one task from the nearest test,
    the required simulation, and the next skill of the path."""
    here, today, uid = reads.of(request), clock.school_day(), user["id"]
    class_ids = [c["id"] for c in here.classes_of_student(user["email"])]
    from .skills import RECENT, behind_lessons, subject_param
    subject = subject_param(request, user, subject)
    here.prefetch(("tests_of_classes", class_ids), ("recent_skills", uid, RECENT), ("attempts_of", uid, "quiz"), ("curriculum",), *_student_reads(uid))       # the tests and the student's facts: one wait
    tests = [t for t in here.tests_of_classes(class_ids) if t["date"] >= today and t.get("subject_id", "math") == subject]
    cards = [card(request, user["id"], t, today) for t in tests]
    nearest = cards[0] if cards else None
    next_id = _next_path_skill(request, user, subject)
    next_skill_row = request.app.state.bank.skill(next_id) if next_id else None
    return {"tests": cards, "task": {"test_id": nearest["id"], **_with_skill_name(request, nearest["task"])} if nearest else None,
            "required_simulations": [{"test_id": c["id"], "date": c["date"], "days_left": c["days_left"]} for c in cards if c["simulation"]["required"]],
            "next_skill": {"id": next_id, "name": next_skill_row["name"]} if next_skill_row else None,
            "behind": behind_lessons(request, user, subject), "subject": subject,
            "weak_tests": [{"test_id": c["id"], "date": c["date"], "days_left": c["days_left"], "number": e["number"], "best": e["best"], "open": e["open"]}
                           for c in cards[:1] for e in c["exercise_tests"] if e["best"] is not None and e["best"] < attempts.PASS_GRADE]}   # the nearest test's card only


def _student_test(request: Request, user: dict, test_id: int) -> dict:
    here = reads.of(request)
    test = here.get_test(test_id)
    mine = {c["id"] for c in here.classes_of_student(user["email"])}
    if test is None or test["removed_at"] or not (test["class_id"] in mine or allowed(user["roles"], "*")):
        raise HTTPException(404, "המבחן לא נמצא")
    return test


@router.get("/tests/{test_id}")
def test_card(test_id: int, request: Request, user: dict = Depends(learner)) -> dict:
    reads.of(request).prefetch(("get_test", test_id), *_student_reads(user["id"]))
    return card(request, user["id"], _student_test(request, user, test_id), clock.school_day())


# ---- starting an exercise test or the simulation (reading, answering and submitting use the /api/attempts routes) ----

def _start(request: Request, user: dict, test: dict, kind: str, scope: str, share: float) -> dict:
    """Resume the student's open attempt of this scope, else draw a new one (questions weighted toward weak skills when `share`)."""
    from .quizzes import view
    store, bank, now = request.app.state.store, request.app.state.bank, clock.now()
    facts = facts_for(request, user["id"], test, clock.school_day())
    mine = [r for r in (facts["exercise"][int(scope.split(":")[1])] if kind == "exercise_test" else [facts["simulation"]] if facts["simulation"] else [])]
    for row in mine:
        if attempts.is_open(row) or kind == "simulation":           # open: resume; the simulation is taken once, so its result comes back
            return view(request, row)
    drawn = exam.draw(bank, test["lessons"], facts["states"], test["questions"], share=share, weak_before=facts["weak_before"], used=facts["used"])
    if not drawn["questions"]:
        raise HTTPException(409, "עוד לא התחלתם מיומנויות בשיעורים של המבחן. קודם מתרגלים במסלול.")
    row = store.create_attempt(user["id"], kind, scope, now, now + timedelta(minutes=test["minutes"]), drawn["questions"])
    return view(request, row)


@router.post("/tests/{test_id}/exercise/{number}/start")
def start_exercise(test_id: int, number: int, request: Request, user: dict = Depends(learner)) -> dict:
    if number not in exam.EXERCISE_SHARE:
        raise HTTPException(404, "מבחן התרגול לא נמצא")
    test = _student_test(request, user, test_id)
    return _start(request, user, test, "exercise_test", f"{test_id}:{number}", exam.EXERCISE_SHARE[number])


@router.post("/tests/{test_id}/simulation/start")
def start_simulation(test_id: int, request: Request, user: dict = Depends(learner)) -> dict:
    test = _student_test(request, user, test_id)
    today = clock.school_day()
    p = plan_for(test)
    existing = facts_for(request, user["id"], test, today)["simulation"]
    if not existing and not countdown.sim_open(( test["date"] - today).days, p):
        opens = test["date"] - timedelta(days=p["sim"])
        raise HTTPException(409, f"מבחן הסימולציה ייפתח ב־{opens.day}.{opens.month}" if today < opens else "מבחן הסימולציה נסגר")
    return _start(request, user, test, "simulation", str(test_id), 0.0)
