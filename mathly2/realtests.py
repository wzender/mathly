"""Real tests: a teacher sets one for a class; every student of the class can ask for practice tests (balanced, focused on the weak skills,
or on skills they pick) and simulations (all the material, timed, as many as they like), and has a readiness number that only these tests
move (readiness.py). Nothing is created per student: it is all derived from the test, the student's skill states and their attempts."""
from __future__ import annotations

from datetime import date, timedelta
from datetime import date as Day

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from . import writtentest, attempts, clock, exam, readiness, reads
from .access import allowed, learner, my_classes, need
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


def _kind_of(row: dict) -> str:
    """How a handed-in test moves readiness: simulation, practice, or manual (a practice test on skills the student picked)."""
    if row["kind"] == "simulation":
        return "simulation"
    return "manual" if exam.mode_of_scope(row["scope"]) == "manual" else "practice"


def facts_for(request: Request, user_id: str | None, test: dict, today: date) -> dict:
    """Everything the card, the readiness number and the draws need about one student and one test."""
    store, bank, now, here = request.app.state.store, request.app.state.bank, clock.now(), reads.of(request)
    covered = _covered(bank, test)
    if user_id:
        here.prefetch(*_student_reads(user_id))                      # the reads together (done once per request: a second test reuses them)
    states = {p["skill_id"]: skill_state(p) for p in here.progress_of(user_id)} if user_id else {}
    tid = str(test["id"])

    def mine(kind: str) -> list[dict]:
        rows = here.attempts_of(user_id, kind) if user_id else []
        return [attempts.settle(store, bank, r, now) for r in rows if r["scope"] == tid or r["scope"].startswith(tid + ":")]

    practice, simulations = mine("exercise_test"), mine("simulation")
    done = sorted((r for r in practice + simulations if not attempts.is_open(r)), key=lambda r: r["submitted_at"])
    graded = [r for r in done if r["grade"] is not None]                 # a written simulation waiting for its check does not count yet
    lost = {s["id"] for r in graded for s in _result(request, r)["lost_skills"]}
    used: dict[str, int] = {}
    for r in practice + simulations:
        for q in r["questions"]:
            used[q["key"]] = used.get(q["key"], 0) + 1
    return {"covered": covered, "states": states, "mastered": sum(1 for i in covered if states.get(i) == MASTERED),
            "practice": practice, "simulations": simulations, "done": done, "graded": graded, "results": [(_kind_of(r), r["grade"]) for r in graded],
            "sim_taken": any(r["kind"] == "simulation" for r in done), "used": used,
            "focus_skills": [i for i in covered if (i in lost or states.get(i) == "learning") and bank.question_keys(i)]}


def _result(request: Request, row: dict) -> dict:
    if writtentest.is_written(row):
        return writtentest.result(request.app.state.bank, row, request.app.state.store.work_of(row["user_id"], row["id"]))
    return attempts.result(request.app.state.bank, row)


def mastered_share(facts: dict) -> float:
    """The share of the test's skills mastered (deepening counts toward readiness)."""
    return facts["mastered"] / len(facts["covered"]) if facts["covered"] else 0.0


def readiness_for(facts: dict) -> dict:
    return readiness.compute(facts["results"], mastered_share(facts))


def readiness_change(request: Request, row: dict) -> dict | None:
    """For a handed-in practice test or simulation: what it did to its test's readiness number (before, after, gain, a new level)."""
    if row["kind"] not in ("exercise_test", "simulation") or attempts.is_open(row) or row["grade"] is None:
        return None
    test_id = row["scope"].split(":")[0]
    test = request.app.state.store.get_test(int(test_id)) if test_id.isdigit() else None
    if test is None:
        return None
    facts = facts_for(request, row["user_id"], test, clock.school_day())
    before = [(_kind_of(r), r["grade"]) for r in facts["graded"] if r["submitted_at"] < row["submitted_at"]]
    return readiness.change(before, (_kind_of(row), row["grade"]), mastered_share(facts))


def _title(row: dict) -> str:
    return "מבחן סימולציה" if row["kind"] == "simulation" else exam.TITLES[exam.mode_of_scope(row["scope"])]


def card(request: Request, user_id: str | None, test: dict, today: date) -> dict:
    """A test as its student sees it: the readiness number and what moves it, the practice tests by mode, the simulations, and the trail
    of handed-in tests with what each added."""
    bank = request.app.state.bank
    facts = facts_for(request, user_id, test, today)
    days_left = (test["date"] - today).days
    skill_row = lambda i: {"id": i, "name": bank.skill(i)["name"]}
    open_of = lambda rows: next((r["id"] for r in reversed(rows) if attempts.is_open(r)), None)
    by_mode = {m: [r for r in facts["practice"] if exam.mode_of_scope(r["scope"]) == m] for m in exam.TITLES}
    trail, before = [], []
    for row in facts["done"]:
        if row["grade"] is None:                                        # handed in, waiting for its check: no gain yet
            trail.append({"attempt": row["id"], "kind": row["kind"], "title": _title(row), "grade": None, "checking": True, "gain": 0,
                          "number": None, "after": None, "at": row["submitted_at"].isoformat()})
            continue
        moved = readiness.change(before, (_kind_of(row), row["grade"]), mastered_share(facts))
        before.append((_kind_of(row), row["grade"]))
        trail.append({"attempt": row["id"], "kind": row["kind"], "title": _title(row), "grade": row["grade"], "gain": moved["gain"],
                      "number": int(row["scope"].split(":")[1]) if row["kind"] == "exercise_test" else None,
                      "after": moved["after"], "at": row["submitted_at"].isoformat()})
    lessons = {l["id"]: l["name"] for l in bank.lessons}
    return {"id": test["id"], "date": test["date"].isoformat(), "days_left": days_left, "note": test["note"], "subject_id": test.get("subject_id", "math"),
            "lessons": [{"id": i, "name": n} for i, n in zip(test["lessons"], lesson_names(request, test["lessons"]))],
            "questions": test["questions"], "minutes": test["minutes"], "readiness": readiness_for(facts),
            "practice": {"balanced": {"number": exam.BALANCED, "size": test["questions"], "open": open_of(by_mode["balanced"])},
                         "focus": {"number": exam.FOCUS, "size": exam.FOCUS_SIZE, "open": open_of(by_mode["focus"]),
                                   "skills": [skill_row(i) for i in facts["focus_skills"]]},
                         "manual": {"number": exam.MANUAL, "size": test["questions"], "open": open_of(by_mode["manual"]),
                                    "skills": [{**skill_row(i), "lesson": lessons.get(bank.skill(i)["unit"], ""),
                                                "state": facts["states"].get(i, "not_started")} for i in facts["covered"]]}},
            "simulation": {"open": open_of(facts["simulations"]), "taken": sum(1 for r in facts["done"] if r["kind"] == "simulation"),
                           "best": readiness_for(facts)["simulation_best"]},
            "trail": trail[::-1]}


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
                         "readiness": readiness_for(facts)})          # readiness: the number, and how many practice tests and simulations
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
    """The student's home: the upcoming tests (nearest first) with their readiness, the lesson map, and the next skill of the path."""
    here, today, uid = reads.of(request), clock.school_day(), user["id"]
    class_ids = [c["id"] for c in my_classes(request, user)]
    from . import rounds
    from .skills import RECENT, behind_lessons, lesson_map, subject_param
    subject = subject_param(request, user, subject)
    here.prefetch(("tests_of_classes", class_ids), ("recent_skills", uid, RECENT), ("attempts_of", uid, "quiz"), ("attempts_of", uid, rounds.KIND), ("curriculum",), ("daily_correct", uid), *_student_reads(uid))       # the tests and the student's facts: one wait
    tests = [t for t in here.tests_of_classes(class_ids) if t["date"] >= today and t.get("subject_id", "math") == subject]
    cards = [card(request, user["id"], t, today) for t in tests]
    next_id = _next_path_skill(request, user, subject)
    next_skill_row = request.app.state.bank.skill(next_id) if next_id else None
    return {"tests": cards,
            "next_skill": {"id": next_id, "name": next_skill_row["name"]} if next_skill_row else None,
            "behind": behind_lessons(request, user, subject), "subject": subject, "map": lesson_map(request, user, subject)}


def _student_test(request: Request, user: dict, test_id: int) -> dict:
    here = reads.of(request)
    test = here.get_test(test_id)
    mine = {c["id"] for c in my_classes(request, user)}
    if test is None or test["removed_at"] or not (test["class_id"] in mine or allowed(user["roles"], "*")):
        raise HTTPException(404, "המבחן לא נמצא")
    return test


@router.get("/tests/{test_id}")
def test_card(test_id: int, request: Request, user: dict = Depends(learner)) -> dict:
    reads.of(request).prefetch(("get_test", test_id), *_student_reads(user["id"]))
    return card(request, user["id"], _student_test(request, user, test_id), clock.school_day())


# ---- starting a practice test or a simulation (reading, answering and submitting use the /api/attempts routes) ----

class PracticeBody(BaseModel):
    mode: str = Field(pattern="^(balanced|focus|manual)$")
    skills: list[str] = Field(default_factory=list, max_length=200)    # manual: the skills to practise


def _new(request: Request, user: dict, test: dict, kind: str, scope: str, questions: list[dict]) -> dict:
    from .quizzes import view
    now = clock.now()
    return view(request, request.app.state.store.create_attempt(user["id"], kind, scope, now, now + timedelta(minutes=test["minutes"]), questions))


def _practice(request: Request, user: dict, test: dict, mode: str, skills: list[str] | None = None, number: int | None = None) -> dict:
    """Resume this mode's open practice test (not a manual one: a new choice is a new test), else draw a new one."""
    from .quizzes import view
    bank = request.app.state.bank
    facts = facts_for(request, user["id"], test, clock.school_day())
    number = number or exam.NUMBER_OF[mode]
    scope = f"{test['id']}:{number}"
    if mode != "manual":
        for row in facts["practice"]:
            if row["scope"] == scope and attempts.is_open(row):
                return view(request, row)
    rng = getattr(request.app.state, "quiz_rng", None)
    if mode == "focus":
        if not facts["focus_skills"]:
            raise HTTPException(409, "אין כרגע מיומנויות שהתקשיתם בהן. נסו מבחן מאוזן או סימולציה.")
        drawn = exam.draw_focus(bank, facts["focus_skills"], used=facts["used"], rng=rng)
    elif mode == "manual":
        chosen = [i for i in dict.fromkeys(skills or []) if i in facts["covered"]]
        if not chosen:
            raise HTTPException(422, "בחרו לפחות מיומנות אחת מהחומר של המבחן")
        drawn = exam.draw_focus(bank, chosen, n=test["questions"], used=facts["used"], rng=rng)
    else:
        drawn = exam.draw(bank, test["lessons"], facts["states"], test["questions"], used=facts["used"], include_unstarted=True, rng=rng)["questions"]
    if not drawn:
        raise HTTPException(409, "אין עדיין שאלות בחומר של המבחן")
    return _new(request, user, test, "exercise_test", scope, drawn)


@router.post("/tests/{test_id}/practice/start")
def start_practice(test_id: int, body: PracticeBody, request: Request, user: dict = Depends(learner)) -> dict:
    """A practice test: balanced (all the material, evenly), focus (the skills that lost points or are still being learned, 15 questions),
    or manual (the skills the student picked)."""
    return _practice(request, user, _student_test(request, user, test_id), body.mode, body.skills)


@router.post("/tests/{test_id}/exercise/{number}/start")
def start_exercise(test_id: int, number: int, request: Request, user: dict = Depends(learner),
                   all_skills: bool = Query(False, description="kept for old links: every practice test now draws from all the material")) -> dict:
    """An older address of a practice test by number (1, 2: balanced; 3: focus), as in a teacher's assignment."""
    mode = exam.MODE_OF.get(number)
    if mode is None or mode == "manual":
        raise HTTPException(404, "מבחן התרגול לא נמצא")
    return _practice(request, user, _student_test(request, user, test_id), mode, number=number)


@router.post("/tests/{test_id}/simulation/start")
def start_simulation(test_id: int, request: Request, user: dict = Depends(learner),
                     all_skills: bool = Query(False, description="kept for old links: a simulation always draws from all the material")) -> dict:
    """A simulation: all the test's material evenly, the test's length and time, no choice. As many as the student asks for; an open one
    resumes."""
    from .quizzes import view
    test = _student_test(request, user, test_id)
    facts = facts_for(request, user["id"], test, clock.school_day())
    for row in facts["simulations"]:
        if attempts.is_open(row):
            return view(request, row)
    drawn = exam.draw(request.app.state.bank, test["lessons"], facts["states"], test["questions"], used=facts["used"], include_unstarted=True,
                      rng=getattr(request.app.state, "quiz_rng", None))["questions"]
    if not drawn:
        raise HTTPException(409, "אין עדיין שאלות בחומר של המבחן")
    return _new(request, user, test, "simulation", str(test_id), drawn)
