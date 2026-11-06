"""The student's own overviews: everything they owe (the task list) and every grade the server holds (the grades page).

Both are read models over what other modules keep: assignments and worksheets (app/assignments.py, app/worksheets.py),
final quizzes (app/quiz_modes.py), unit-quiz sittings and teacher reviews (app/answer_routes.py). They answer for the
signed-in student only and take no student id. A part that cannot be read comes back as None, and the page says so,
rather than the whole answer failing.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from fastapi.responses import JSONResponse

from .answer_scans import ScanError
from .quiz_modes import QuizModesUnavailable, hide_results, official_grades
from .quiz_grades import sitting_view

log = logging.getLogger("mathly.student_views")


def unit_of_assignment(assignment: dict) -> str | None:
    """The unit an assignment is about, from its items (a worksheet alone says none)."""
    from .math_skills import algebra9
    skills = {sk["id"]: sk["unit"] for sk in algebra9()["skills"]}
    for item in assignment.get("items") or []:
        if item.get("kind") == "skill" and item.get("id") in skills:
            return skills[item["id"]]
        if item.get("kind") == "unit_quiz":
            return item.get("unit")
        if item.get("kind") == "exam" and item.get("units"):
            return item["units"][0]
    return None


def install_student_view_routes(app, signed_in, units_of):
    def reply(value):
        return JSONResponse(value, headers={"Cache-Control": "no-store"})

    def student(user) -> dict:
        if not user or not user.get("id"):
            raise HTTPException(401, "sign in required")
        return user

    def assignments(user):
        try:
            return app.state.assignments_for(user)
        except HTTPException:
            return None   # the assignments are not set up or cannot be read

    def finals(user):
        try:
            return app.state.final_offers(user)
        except QuizModesUnavailable:
            return None

    @app.get("/api/math/my-tasks")
    def my_tasks(user=Depends(signed_in)):
        """What the student owes: their assignments (with the hand-ins that tell their state) and the final quizzes
        open to them now. Returned worksheets are among the assignments' submissions (state "returned")."""
        user = student(user)
        return reply({"assignments": assignments(user), "finals": finals(user)})

    def quiz_units(user) -> list[dict]:
        from .math_skills import algebra9
        mine = set()
        for row in user.get("classes") or []:
            mine |= set(units_of(row))
        return [u for u in algebra9()["units"] if "quiz" in u and (not user.get("classes") or u["id"] in mine)]

    def released(views) -> set[str] | None:
        ids = {v["window_id"] for v in views if v.get("mode") == "final" and v.get("window_id")}
        if not ids:
            return set()
        try:
            return {w["id"] for w in app.state.quiz_modes.windows_by_ids(ids) if w.get("released_at")}
        except QuizModesUnavailable:
            return set()   # finals cannot be told released: their grades stay hidden

    @app.get("/api/math/my-grades")
    def my_grades(user=Depends(signed_in)):
        """Every grade the server holds for the student, by unit: the official grade (the latest final sitting, once
        its results are released), the practice sittings (best and latest), and the checked worksheets; with what
        still waits for a check and the teacher's comments the student has not opened."""
        user = student(user)
        units, failed = quiz_units(user), False
        views = []
        for unit in units:
            try:
                views += [v for v in (sitting_view(r) for r in app.state.answers.quiz(user["id"], "list", unit_id=unit["id"])) if v]
            except ScanError:
                failed = True
        open_results = released(views)
        shown = [({**v, "released": True} if v.get("mode") != "final" or v.get("window_id") in open_results else hide_results(v))
                 for v in views]
        out = []
        for unit in units:
            mine = sorted((v for v in shown if v["unit_id"] == unit["id"]), key=lambda v: str(v.get("submitted_at") or ""))
            practice = [v for v in mine if v.get("mode") != "final"]
            graded = [v for v in practice if v.get("grade") is not None]
            official = official_grades(mine).get(unit["id"])
            out.append({"unit_id": unit["id"], "name": unit["name"], "official": official,
                        "practice_best": max(graded, key=lambda v: v["grade"]) if graded else None,
                        "practice_latest": practice[-1] if practice else None, "sittings": mine[::-1]})
        work = assignments(user)
        sheets = None
        if work is not None and work.get("submissions") is not None:
            titles = {w["id"]: w["title"] for w in work.get("worksheets") or []}
            owner = {i["id"]: a for a in work["assignments"] for i in a["items"] if i.get("kind") == "worksheet"}
            sheets = [{**sub, "title": titles.get(sub["worksheet_id"], ""),
                       "assignment": (owner.get(sub["worksheet_id"]) or {}).get("title", ""),
                       "unit_id": unit_of_assignment(owner.get(sub["worksheet_id"]) or {})}
                      for sub in work["submissions"]]
        try:
            comments = app.state.answers.review(user["id"], "unseen")
        except ScanError:
            comments = None
        return reply({"units": out, "quizzes_known": not failed, "worksheets": sheets, "comments": comments})
