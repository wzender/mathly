"""A class's progress for its teacher (PRD TCH-7, TCH-10): per lesson, never per skill, with the periods and the readiness per
student. Nothing is stored: it is all read from the students' progress, quizzes and tests, the lessons' dates and the bank."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request

from . import attempts, clock, readiness, reads
from .access import need
from .learning import LEARNING, MASTERED, NOT_STARTED, skill_state
from .realtests import _my_class, facts_for, prime_students, readiness_for
from .store import _when

router = APIRouter(prefix="/api/classes")

MONTHS = {"ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12, "ינואר": 1, "פברואר": 2, "מרץ": 3, "אפריל": 4, "מאי": 5, "יוני": 6}
PERIODS = ({"id": 1, "label": "ספט׳–דצמ׳"}, {"id": 2, "label": "ינו׳–יוני"})


def period_of_month(month: int) -> int:
    return 1 if 9 <= month <= 12 else 2


def school_year(today: date) -> int:
    """The calendar year in which this school year began (it starts in September)."""
    return today.year if today.month >= 9 else today.year - 1


def period_end(period: int, today: date) -> date:
    year = school_year(today)
    return date(year, 12, 31) if period == 1 else date(year + 1, 6, 30)


def lesson_period(lesson: dict, due: date | None) -> int:
    """By the lesson's date in the curriculum or, without one, by the last month of the bank's month for it."""
    if due:
        return period_of_month(due.month)
    month = MONTHS.get(str(lesson.get("when", "")).split("–")[-1].strip())
    return period_of_month(month) if month else 2


def _day(value) -> date | None:
    if not value:
        return None
    try:
        moment = value if isinstance(value, datetime) else _when(value)
    except ValueError:
        return None
    return clock.school_day(moment) if moment.tzinfo else moment.date()


def state_on(progress: dict | None, end: date, today: date) -> str:
    """The skill's state at the end of a period (today's state while the period has not ended). Mastery never goes away, so the stored times say."""
    if end >= today:
        return skill_state(progress)
    if progress:
        mastered, started = _day(progress.get("mastered_at")), _day(progress.get("started_at"))
        if mastered and mastered <= end:
            return MASTERED
        if (started and started <= end) or (mastered and mastered <= end):
            return LEARNING
    return NOT_STARTED


def best_quiz(rows: list[dict], end: date, today: date) -> int | None:
    """The best grade of the quizzes handed in by the end of the period."""
    grades = [r["grade"] for r in rows if r.get("submitted_at") and r.get("grade") is not None and (end >= today or _day(r["submitted_at"]) <= end)]
    return max(grades) if grades else None


@router.get("/{class_id}/progress")
def class_progress(class_id: int, request: Request, period: int | None = None, user: dict = Depends(need("class.teach"))) -> dict:
    klass = _my_class(request, user, class_id)
    store, bank, here = request.app.state.store, request.app.state.bank, reads.of(request)
    today = clock.school_day()
    current = period_of_month(today.month)
    if period is None:
        period = current
    if period not in (1, 2):
        raise HTTPException(422, "תקופה לא מוכרת")
    end = period_end(period, today)
    members = store.members(klass["id"])
    ids = [m["user_id"] for m in members if m["user_id"]]
    here.prefetch(("curriculum",), ("tests_of_classes", [klass["id"]]))
    prime_students(request, ids, kinds=("exercise_test", "simulation", "quiz"))
    dates = here.curriculum()
    lessons = [l for l in bank.lessons_with_skills() if lesson_period(l, dates.get(l["id"])) == period]
    now_view = end >= today
    students = []
    for m in members:
        uid = m["user_id"]
        states = {p["skill_id"]: p for p in here.progress_of(uid)} if uid else {}
        quizzes: dict[str, list[dict]] = {}
        for row in (here.attempts_of(uid, "quiz") if uid else []):
            quizzes.setdefault(row["scope"], []).append(row)
        coverage = {}
        for lesson in lessons:
            mine = {s["id"]: state_on(states.get(s["id"]), end, today) for s in lesson["skills"]}
            best = best_quiz(quizzes.get(lesson["id"], []), end, today)
            mastered = sum(1 for v in mine.values() if v == MASTERED)
            passed = any(r.get("submitted_at") and r["grade"] is not None and r["grade"] >= attempts.PASS_GRADE and (now_view or _day(r["submitted_at"]) <= end)
                         for r in quizzes.get(lesson["id"], []))
            completed = passed or (bool(mine) and mastered == len(mine))
            due = dates.get(lesson["id"])
            started = best is not None or any(v != NOT_STARTED for v in mine.values())
            coverage[lesson["id"]] = {"state": "completed" if completed else "learning" if started else "not_started",
                                      "percent": round(100 * mastered / len(mine)) if mine else 0, "best": best, "completed": completed,
                                      "behind": bool(now_view and due and due < today and not completed)}
        students.append({"email": m["email"], "signed_in": bool(uid), "lessons": coverage})
    nearest = next((t for t in sorted(store.tests_of_classes([klass["id"]]), key=lambda t: t["date"]) if t["date"] >= today), None)
    test = None
    if nearest:
        rows = []
        for m in members:
            facts = facts_for(request, m["user_id"], nearest, today)
            ready = readiness_for(facts)
            covered = len(facts["covered"])
            rows.append({"email": m["email"], "signed_in": bool(m["user_id"]), "readiness": ready,
                         "mastery": round(100 * facts["mastered"] / covered) if covered else None,          # shown beside it; not part of it
                         "practice": ready["practice_best"], "simulation": ready["simulation_best"],
                         "practices": ready["practices"], "simulations": ready["simulations"]})
        names = {l["id"]: l["name"] for l in bank.lessons}
        test = {"id": nearest["id"], "date": nearest["date"].isoformat(), "days_left": (nearest["date"] - today).days,
                "lessons": [names.get(i, i) for i in nearest["lessons"]], "students": rows}
    return {"class": {"id": klass["id"], "name": klass["name"]}, "period": period, "current_period": current, "as_of": min(end, today).isoformat(),
            "periods": [{**p, "current": p["id"] == current} for p in PERIODS],
            "lessons": [{"id": l["id"], "name": l["name"], "due_date": dates[l["id"]].isoformat() if l["id"] in dates else None} for l in lessons],
            "students": students, "test": test}


# ---- each student's activity: how much and how long, in all and day by day ----

ACTIVITY_DAYS = (7, 14, 30)
TEST_KINDS = ("quiz", "exercise_test", "simulation")
TEST_CAP = 120 * 60                  # a quiz or test counts at most two hours (one left open is not time spent)


@router.get("/{class_id}/activity")
def class_activity(class_id: int, request: Request, days: int = 14, user: dict = Depends(need("class.teach"))) -> dict:
    """For each student of the class: practice answers (right ones too), the estimated time, and quizzes and tests handed in, since the
    school year began and over the last `days` days, with each of those days. Time: practice from the view m2_daily_practice (the gaps
    between answers), quizzes and tests from start to hand-in."""
    if days not in ACTIVITY_DAYS:
        raise HTTPException(422, "טווח לא מוכר")
    klass = _my_class(request, user, class_id)
    store, here, today = request.app.state.store, reads.of(request), clock.school_day()
    start = date(school_year(today), 9, 1)
    first = today - timedelta(days=days - 1)
    members = store.members(klass["id"])
    ids = [m["user_id"] for m in members if m["user_id"]]
    prime_students(request, ids, kinds=TEST_KINDS)
    practice: dict[str, dict[date, dict]] = {}
    for r in store.daily_practice(ids, start):
        practice.setdefault(r["user_id"], {})[r["day"]] = r
    students = []
    for m in members:
        uid = m["user_id"]
        by_day: dict[date, dict] = {d: {"answers": r["answers"], "correct": r["correct"], "seconds": r["seconds"], "tests": 0}
                                    for d, r in (practice.get(uid, {}) if uid else {}).items()}
        for kind in TEST_KINDS:
            for row in (here.attempts_of(uid, kind) if uid else []):
                done, began = _when(row.get("submitted_at")), _when(row.get("started_at"))
                if not done or not began:
                    continue
                day = clock.school_day(began)
                if day < start:
                    continue
                cell = by_day.setdefault(day, {"answers": 0, "correct": 0, "seconds": 0, "tests": 0})
                cell["tests"] += 1
                cell["seconds"] += int(min(max((done - began).total_seconds(), 0), TEST_CAP))

        def total(cells: list[dict]) -> dict:
            return {"answers": sum(c["answers"] for c in cells), "correct": sum(c["correct"] for c in cells),
                    "minutes": round(sum(c["seconds"] for c in cells) / 60), "tests": sum(c["tests"] for c in cells),
                    "days": sum(1 for c in cells if c["answers"] or c["tests"])}

        recent = [(first + timedelta(days=i)) for i in range(days)]
        empty = {"answers": 0, "correct": 0, "seconds": 0, "tests": 0}
        active = [d for d, c in by_day.items() if c["answers"] or c["tests"]]
        students.append({"email": m["email"], "signed_in": bool(uid), "total": total(list(by_day.values())),
                         "recent": total([by_day.get(d, empty) for d in recent]), "last_day": max(active).isoformat() if active else None,
                         "daily": [{"day": d.isoformat(), **{k: v for k, v in by_day.get(d, empty).items() if k != "seconds"},
                                    "minutes": round(by_day.get(d, empty)["seconds"] / 60)} for d in recent]})
    students.sort(key=lambda s: (-s["recent"]["answers"], s["email"]))
    return {"class": {"id": klass["id"], "name": klass["name"]}, "days": days, "since": start.isoformat(), "students": students}
