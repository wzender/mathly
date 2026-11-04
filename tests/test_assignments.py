"""Assignments: what a class teacher asks their class to do. Storage is in memory; the migration runs on real PostgreSQL."""
import asyncio
import uuid
from pathlib import Path

import httpx
import pytest

from app.answer_scans import ScanError
from app.assignments import Assignments, AssignmentsUnavailable
from app.main import create_app
from app.math_skills import algebra9
from scan_support import BOOTSTRAP, answer_store, postgres_server

TEACHER, STUDENT, OTHER_TEACHER, OUTSIDER, MANAGER, PUPIL4 = "t-id", "s-id", "o-id", "x-id", "m-id", "p-id"
EMAILS = {TEACHER: "teacher@x.test", STUDENT: "student@x.test", OTHER_TEACHER: "other@x.test",
          OUTSIDER: "out@x.test", MANAGER: "boss@x.test", PUPIL4: "pupil4@x.test"}
UNITS = algebra9()["units"]
NO_QUIZ = next(u["id"] for u in UNITS if "quiz" not in u)


class ClassAuth:
    url, key, secret = "https://test.invalid", "public-test", "server-test"
    developers = frozenset()
    teachers = frozenset({"boss@x.test"})   # a manager

    def __init__(self):
        self.rows = [
            {"id": 3, "name": "ט׳1", "lessons": ["t", "k", NO_QUIZ], "teachers": ["teacher@x.test"],
             "emails": ["student@x.test", "teacher@x.test"], "nicknames": {}, "exams": []},
            {"id": 4, "name": "ט׳2", "lessons": ["t"], "teachers": ["other@x.test"],
             "emails": ["pupil4@x.test", "other@x.test"], "nicknames": {}, "exams": []}]

    def user(self, token):
        return {"id": token, "email": EMAILS[token]} if token in EMAILS else None

    def classes(self, fresh=False):
        return self.rows

    def access_for(self, _id, **kwargs):
        return None


class MemoryAssignments(Assignments):
    configured = True

    def __init__(self, fail=False):
        self.rows, self.fail = {}, fail

    def _check(self):
        if self.fail:
            raise AssignmentsUnavailable("assignments_unavailable")

    def for_classes(self, class_ids):
        self._check()
        return sorted((r for r in self.rows.values() if r["class_id"] in class_ids), key=lambda r: r["due_on"], reverse=True)

    def get(self, assignment_id):
        self._check()
        return self.rows.get(assignment_id)

    def add(self, row):
        self._check()
        row = {**row, "id": str(uuid.uuid4()), "created_at": "2026-11-04T08:00:00+00:00", "updated_at": "2026-11-04T08:00:00+00:00"}
        self.rows[row["id"]] = row
        return row

    def update(self, assignment_id, fields):
        self._check()
        self.rows[assignment_id] = {**self.rows[assignment_id], **fields}
        return self.rows[assignment_id]

    def remove(self, assignment_id):
        self._check()
        self.rows.pop(assignment_id, None)


class Sittings:
    """The server's unit-quiz sittings (app/quiz_grades.py): quiz(user, "list", unit_id=...)."""
    configured = True

    def __init__(self, by_user=None, fail=False):
        self.by_user, self.fail = by_user or {}, fail

    def quiz(self, user_id, action, **data):
        if self.fail:
            raise ScanError(503, "quiz_sittings_unavailable")
        return [s for s in self.by_user.get(user_id, []) if s["unit_id"] == data["unit_id"]]


def make_app(store=None, sittings=None):
    app = create_app(auth=ClassAuth())
    app.state.assignments = store or MemoryAssignments()
    app.state.answers = sittings or Sittings()
    return app


def client(app, user):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             headers={"Authorization": f"Bearer {user}"})


GOOD = {"title": "חזרה לפני המבחן", "note": "בהצלחה", "due_on": "2026-11-12",
        "items": [{"kind": "skill", "id": "t_ext"}, {"kind": "unit_quiz", "unit": "k"},
                  {"kind": "exam", "units": ["k", "t"]}]}   # exam units are kept sorted


def test_the_class_teacher_creates_lists_edits_and_deletes_assignments():
    store = MemoryAssignments()
    app = make_app(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            made = await teacher.post("/api/classes/3/assignments", json=GOOD)
            assert made.status_code == 201
            row = made.json()
            assert (row["title"], row["note"], row["due_on"], row["class_id"]) == ("חזרה לפני המבחן", "בהצלחה", "2026-11-12", 3)
            assert row["items"] == GOOD["items"] and row["created_by_email"] == "teacher@x.test"
            assert [r["id"] for r in store.rows.values()] == [row["id"]] and store.rows[row["id"]]["class_id"] == 3
            listed = (await teacher.get("/api/classes/3/assignments")).json()["assignments"]
            assert [r["id"] for r in listed] == [row["id"]]
            edited = await teacher.put(f"/api/classes/3/assignments/{row['id']}",
                                       json={**GOOD, "title": "  חזרה   מורחבת ", "due_on": "2026-11-14",
                                             "items": [{"kind": "skill", "id": "t_ext"}, {"kind": "skill", "id": "t_ext"}]})
            assert edited.status_code == 200
            assert (edited.json()["title"], edited.json()["due_on"], edited.json()["items"]) == (
                "חזרה מורחבת", "2026-11-14", [{"kind": "skill", "id": "t_ext"}])   # spacing tidied, a repeated item once
            gone = await teacher.delete(f"/api/classes/3/assignments/{row['id']}")
            assert gone.json() == {"ok": True} and not store.rows
            assert (await teacher.delete(f"/api/classes/3/assignments/{row['id']}")).status_code == 404
    asyncio.run(check())
    assert [a["kind"] for a in app.state.actions.recent()].count("assignment_saved") == 2


def test_an_assignment_is_checked_against_the_classs_units():
    app = make_app()
    skills = algebra9()["skills"]
    class_skills = [s["id"] for s in skills if s["unit"] in ("t", "t2", "k", "i", NO_QUIZ)]
    with_items = lambda *items: {**GOOD, "items": list(items)}
    bad = [
        with_items({"kind": "skill", "id": "no_such_skill"}),
        with_items({"kind": "unit_quiz", "unit": NO_QUIZ}),                  # a unit without a quiz
        with_items({"kind": "exam", "units": []}),
        with_items({"kind": "exam", "units": ["t", "t"]}),
        with_items({"kind": "homework"}), with_items("t_ext"), with_items(),
        {**GOOD, "items": [{"kind": "skill", "id": sid} for sid in class_skills[:21]]},       # one too many
        {**GOOD, "title": ""}, {**GOOD, "title": "   "}, {**GOOD, "title": "א" * 81}, {**GOOD, "note": "א" * 501},
        {**GOOD, "due_on": "2026-13-45"}, {**GOOD, "due_on": "12/11/2026"}, {**GOOD, "due_on": "2026-11-12T10:00:00"},
        {**GOOD, "due_on": ""}, {**GOOD, "due_on": 20261112}, {k: v for k, v in GOOD.items() if k != "due_on"},
        {**GOOD, "items": "t_ext"}]

    async def check():
        async with client(app, TEACHER) as teacher:
            for body in bad:
                assert (await teacher.post("/api/classes/3/assignments", json=body)).status_code == 400, body
            assert (await teacher.post("/api/classes/3/assignments", json=GOOD)).status_code == 201
            twenty = [{"kind": "skill", "id": sid} for sid in class_skills[:20]]
            assert (await teacher.post("/api/classes/3/assignments", json={**GOOD, "items": twenty})).status_code == 201
            assert len(app.state.assignments.rows) == 2   # nothing else was stored
        async with client(app, OTHER_TEACHER) as other:   # class 4 has unit t (and t2, split off from it), not k
            ok = {"kind": "skill", "id": "t_ext"}
            for foreign in ({"kind": "skill", "id": next(s["id"] for s in skills if s["unit"] == "k")},
                            {"kind": "unit_quiz", "unit": "k"}, {"kind": "exam", "units": ["t", "k"]}):
                assert (await other.post("/api/classes/4/assignments", json=with_items(ok, foreign))).status_code == 400, foreign
            assert (await other.post("/api/classes/4/assignments", json=with_items(ok, {"kind": "unit_quiz", "unit": "t"}))).status_code == 201
    asyncio.run(check())


def test_only_the_classs_teacher_or_a_manager_may_manage_its_assignments():
    store = MemoryAssignments()
    app = make_app(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            row = (await teacher.post("/api/classes/3/assignments", json=GOOD)).json()
        for who in (STUDENT, OTHER_TEACHER, OUTSIDER):
            async with client(app, who) as c:
                assert (await c.get("/api/classes/3/assignments")).status_code == 403, who
                assert (await c.post("/api/classes/3/assignments", json=GOOD)).status_code == 403, who
                assert (await c.put(f"/api/classes/3/assignments/{row['id']}", json=GOOD)).status_code == 403
                assert (await c.delete(f"/api/classes/3/assignments/{row['id']}")).status_code == 403
        assert len(store.rows) == 1
        async with client(app, MANAGER) as manager:
            assert (await manager.post("/api/classes/3/assignments", json=GOOD)).status_code == 201
            assert (await manager.post("/api/classes/99/assignments", json=GOOD)).status_code == 404
        async with client(app, OTHER_TEACHER) as other:   # their own class, but not another class's assignment
            assert (await other.delete(f"/api/classes/4/assignments/{row['id']}")).status_code == 404
            assert (await other.put(f"/api/classes/4/assignments/{row['id']}", json=GOOD)).status_code == 404
            assert (await other.get("/api/classes/4/assignments")).json() == {"assignments": []}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as guest:
            assert (await guest.get("/api/classes/3/assignments")).status_code == 401
    asyncio.run(check())


def test_students_get_only_their_classs_assignments_and_when_they_handed_in_each_unit_quiz():
    store = MemoryAssignments()
    app = make_app(store, Sittings({STUDENT: [
        {"id": "s1", "unit_id": "k", "submitted_at": "2026-11-05T10:00:00Z", "grade": 80},
        {"id": "s2", "unit_id": "t", "submitted_at": "2026-11-01T10:00:00Z", "grade": 90}]}))

    async def check():
        async with client(app, TEACHER) as teacher, client(app, OTHER_TEACHER) as other:
            mine = (await teacher.post("/api/classes/3/assignments", json=GOOD)).json()
            await other.post("/api/classes/4/assignments", json={**GOOD, "title": "של כיתה אחרת", "items": [{"kind": "skill", "id": "t_ext"}]})
        async with client(app, STUDENT) as student:
            r = await student.get("/api/math/assignments")
            assert r.status_code == 200
            data = r.json()
            assert [a["id"] for a in data["assignments"]] == [mine["id"]] and data["assignments"][0]["class_name"] == "ט׳1"
            assert "created_by_email" not in data["assignments"][0] and "teacher@x.test" not in r.text   # no teacher email
            assert data["sittings"] == [{"unit_id": "k", "submitted_at": "2026-11-05T10:00:00Z"}]      # only the assigned unit's
            assert len(data["today"]) == 10
        async with client(app, OUTSIDER) as outsider:   # in no class while classes exist: not let in at all
            assert (await outsider.get("/api/math/assignments")).status_code == 403
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as guest:
            assert (await guest.get("/api/math/assignments")).status_code == 401
    asyncio.run(check())


def test_without_the_servers_sittings_or_table_the_answers_say_so():
    store = MemoryAssignments()
    app = make_app(store, Sittings(fail=True))

    async def check():
        async with client(app, TEACHER) as teacher:
            await teacher.post("/api/classes/3/assignments", json=GOOD)
        async with client(app, STUDENT) as student:
            data = (await student.get("/api/math/assignments")).json()
            assert len(data["assignments"]) == 1 and data["sittings"] is None   # unit-quiz items cannot be told done
        store.fail = True
        async with client(app, STUDENT) as student, client(app, TEACHER) as teacher:
            r = await student.get("/api/math/assignments")
            assert (r.status_code, r.json()["detail"]) == (503, "assignments_unavailable")
            assert (await teacher.post("/api/classes/3/assignments", json=GOOD)).status_code == 503
    asyncio.run(check())


def test_the_migration_is_additive_service_only_and_follows_its_class(postgres_server):
    psycopg = pytest.importorskip("psycopg")
    database = "asg_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute("create database " + database)
    try:
        with psycopg.connect(postgres_server.get_uri(database=database), autocommit=True) as c:
            c.execute(BOOTSTRAP)
            c.execute("insert into classes values (2, 'other class')")
            c.execute(Path("supabase/migrations/20261104210000_math_assignments.sql").read_text())
            assert c.execute("select name from classes order by id").fetchall() == [("existing math class",), ("other class",)]
            c.execute("set role service_role")
            add = lambda cls, items='[{"kind":"skill","id":"t_ext"}]', title="חזרה", due="2026-11-12": c.execute(
                "insert into math_assignments(class_id,title,due_on,items) values(%s,%s,%s,%s::jsonb)", (cls, title, due, items))
            add(1)
            add(1, title="שני")
            add(2)
            for bad in (dict(cls=1, title=""), dict(cls=1, title="א" * 81), dict(cls=1, items="[]"), dict(cls=1, items="{}"),
                        dict(cls=1, items="[" + ",".join(['{"kind":"skill","id":"x"}'] * 21) + "]"), dict(cls=99)):
                with pytest.raises(psycopg.errors.Error):
                    add(**bad)
            c.execute("reset role")
            c.execute("delete from classes where id = 1")   # a deleted class takes its assignments with it
            assert c.execute("select count(*) from math_assignments").fetchone()[0] == 1
            c.execute("set role authenticated")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute("select * from math_assignments")
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute("drop database " + database + " with (force)")


def test_a_student_in_two_classes_gets_the_assignments_of_both_and_none_of_a_third():
    app = make_app()
    app.state.auth.rows[1]["emails"].append("student@x.test")   # the student is in class 4 as well
    app.state.auth.rows.append({"id": 5, "name": "ט׳3", "lessons": ["t"], "teachers": ["other@x.test"],
                                "emails": ["pupil4@x.test"], "nicknames": {}, "exams": []})

    async def check():
        async with client(app, TEACHER) as teacher, client(app, OTHER_TEACHER) as other:
            await teacher.post("/api/classes/3/assignments", json={**GOOD, "title": "כיתה 3"})
            await other.post("/api/classes/4/assignments", json={**GOOD, "title": "כיתה 4", "items": [{"kind": "skill", "id": "t_ext"}]})
            await other.post("/api/classes/5/assignments", json={**GOOD, "title": "כיתה 5", "items": [{"kind": "skill", "id": "t_ext"}]})
        async with client(app, STUDENT) as student:
            got = (await student.get("/api/math/assignments")).json()["assignments"]
            assert sorted((a["title"], a["class_name"]) for a in got) == [("כיתה 3", "ט׳1"), ("כיתה 4", "ט׳2")]
    asyncio.run(check())


# ---- the whole path: a real server and database, a real browser for the student
def test_an_assignment_given_by_the_teacher_is_completed_by_the_student_and_shows_done_in_the_report(answer_store, monkeypatch):
    """The teacher gives a class two skills and a unit quiz. The student's home card follows them as the student finishes
    the skills in the browser and hands the quiz in; the teacher's report then carries what is needed to show the student
    as done, and the rules of the page agree."""
    import socket
    import threading
    import time
    import urllib.parse

    import uvicorn
    from scan_support import OTHER, OWNER, ScanAuth
    from test_answer_browser import session
    from test_sky_browser import answer_skill_right
    from test_unit_quiz import check, quiz_answer
    playwright = pytest.importorskip("playwright.sync_api")
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    mail = lambda uid: uid + "@test.invalid"

    class SchoolAuth(ScanAuth):
        teachers = frozenset()   # nobody is a manager: OTHER is the class teacher, OWNER a student

        def __init__(self):
            self.progress = {}

        def user(self, token):
            return {"id": token, "email": mail(token)} if token in (OWNER, OTHER) else None

        def classes(self, fresh=False):
            return [{"id": 3, "name": "ט׳1", "lessons": ["t", "k"], "teachers": [mail(OTHER)],
                     "emails": [mail(OWNER), mail(OTHER)], "nicknames": {}, "exams": []}]

        def user_accounts(self, emails):
            return {mail(uid): {"id": uid, "name": ""} for uid in (OWNER, OTHER) if mail(uid) in emails}

        def _admin(self, path, method="GET", body=None, prefer=""):
            from app.auth import AuthUnavailable
            table, _, query = path.partition("?")
            if table != "/rest/v1/math_progress":
                raise AuthUnavailable("supabase answered 404: no other tables here")
            if method == "POST":
                self.progress[body["user_id"]] = {"data": body["data"], "updated_at": body["updated_at"]}
                return None
            wanted = dict(urllib.parse.parse_qsl(query))["user_id"]
            ids = wanted.removeprefix("in.(").removesuffix(")").split(",") if wanted.startswith("in.") else [wanted.removeprefix("eq.")]
            return [{"user_id": i, **self.progress[i]} for i in ids if i in self.progress]

    auth = SchoolAuth()
    app = create_app(auth=auth)
    app.state.answers, app.state.assignments = answer_store, MemoryAssignments()
    plan = {"title": "חזרה על הפילוג", "note": "", "due_on": "2099-01-01",
            "items": [{"kind": "skill", "id": "t_ext"}, {"kind": "skill", "id": "t_simplify"}, {"kind": "unit_quiz", "unit": "t"}]}
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            url = f"http://127.0.0.1:{sock.getsockname()[1]}"
            as_ = lambda uid: {"Authorization": f"Bearer {uid}"}
            made = httpx.post(url + "/api/classes/3/assignments", json=plan, headers=as_(OTHER))
            assert made.status_code == 201
            with playwright.sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    page = session(browser, mobile=True).new_page()
                    errors = []
                    page.on("pageerror", lambda e: errors.append(str(e)))
                    page.goto(url)
                    page.locator('.mx-nav [data-view="path"]').click()
                    card = page.locator(".mx-asgs .mx-asg")
                    playwright.expect(card).to_contain_text("חזרה על הפילוג")
                    playwright.expect(card).to_contain_text("0 מתוך 3 הושלמו")
                    playwright.expect(page.locator('.mx-star[data-id="t_ext"] .mx-asg-pin')).to_have_count(1)
                    for skill, count in (("t_ext", 1), ("t_simplify", 2)):          # the student finishes the skills
                        page.locator(f'.mx-star[data-id="{skill}"]').click()
                        answer_skill_right(page)
                        while page.locator(".sky-cele [data-sky=go]").count():
                            page.locator(".sky-cele [data-sky=go]").first.click()
                        page.locator(".mx-x").last.click()
                        playwright.expect(card).to_contain_text(f"{count} מתוך 3 הושלמו")
                    playwright.expect(card.locator("[data-asg-go]")).to_contain_text("בוחן מסכם")    # what is left
                    # the unit quiz: photographed, checked and handed in
                    ids = [quiz_answer(answer_store, i) for i in range(4)]
                    for aid in ids:
                        check(answer_store, aid, 100)
                    handed = httpx.post(url + "/api/math/quiz-sittings", headers=as_(OWNER), json={
                        "unit_id": "t", "attempts": ids, "client_key": str(uuid.uuid4())})
                    assert handed.status_code == 200 and handed.json()["grade"] == 100
                    page.reload()
                    page.locator('.mx-nav [data-view="path"]').click()
                    playwright.expect(page.locator(".mx-asgs .mx-asg")).to_have_count(0)           # nothing open is left
                    playwright.expect(page.locator(".mx-asg-done summary")).to_have_text("הושלמו (1)")
                    assert page.locator(".mx-asg-pin").count() == 0                                # and no markers
                    # what the student's device saved reaches the server; then the teacher's report
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline and not {"t_ext", "t_simplify"} <= set(auth.progress.get(OWNER, {}).get("data", {}).get("done", {})):
                        time.sleep(.2)
                    report = httpx.get(url + "/api/classes/3/report", headers=as_(OTHER)).json()
                    (student,) = report["students"]
                    (assignment,) = report["assignments"]
                    assert assignment["id"] == made.json()["id"] and student["email"] == mail(OWNER)
                    assert {"t_ext", "t_simplify"} <= set(student["progress"]["done"])
                    assert [s["grade"] for s in student["quiz_sittings"]] == [100]
                    seen = page.evaluate("([a, s]) => MathlySky.assignmentState(a, s.progress, s.quiz_sittings)", [assignment, student])
                    assert seen["finished"] and seen["doneCount"] == 3 and not seen["overdue"] and not seen["late"]
                    assert not errors
                finally:
                    browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
