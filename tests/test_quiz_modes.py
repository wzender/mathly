"""Practice and final unit quizzes (app/quiz_modes.py): the teacher's windows and grants, the one final sitting with
the server's clock, the block on practice while a final waits, and results held back until the teacher releases them.
Windows, grants and starts are in memory; answers and sittings are real PostgreSQL (scan_support)."""
import asyncio
import io
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from PIL import Image

from app.auth import ClassConflict
from app.main import create_app
from app.math_skills import algebra9, question_version, quiz_snapshot
from app.quiz_modes import QuizModes, QuizModesUnavailable, deadline_for, official_grades
from scan_support import OTHER, OWNER, ScanAuth, answer_store, postgres_server

TEACHER, OTHER_TEACHER = "teacher-token", "other-teacher-token"
EMAILS = {OWNER: OWNER + "@test.invalid", OTHER: OTHER + "@test.invalid",
          TEACHER: "teacher@x.test", OTHER_TEACHER: "other@x.test"}
T = next(u for u in algebra9()["units"] if u["id"] == "t")


class SchoolAuth(ScanAuth):
    teachers = frozenset()

    def user(self, token):
        return {"id": token, "email": EMAILS[token]} if token in EMAILS else None

    def classes(self, fresh=False):
        return [{"id": 1, "name": "ט׳1", "lessons": ["t"], "teachers": ["teacher@x.test"],
                 "emails": [EMAILS[OWNER], EMAILS[OTHER]], "nicknames": {}, "exams": []},
                {"id": 2, "name": "ט׳2", "lessons": ["t"], "teachers": ["other@x.test"], "emails": [], "nicknames": {},
                 "exams": []}]

    def user_ids(self, emails):
        return {e: uid for uid, e in EMAILS.items() if e in emails and uid in (OWNER, OTHER)}


class MemoryQuizModes(QuizModes):
    configured = True

    def __init__(self):
        self.w, self.g, self.s = {}, {}, {}

    def _new(self, table, row):
        row = {**row, "id": row.get("id") or str(uuid.uuid4()), "created_at": datetime.now(timezone.utc).isoformat()}
        table[row["id"]] = row
        return dict(row)

    def windows(self, class_ids):
        return [dict(w) for w in self.w.values() if w["class_id"] in set(class_ids)]

    def window(self, window_id):
        return dict(self.w[window_id]) if window_id in self.w else None

    def windows_by_ids(self, ids):
        return [dict(self.w[i]) for i in ids if i in self.w]

    def add_window(self, row):
        return self._new(self.w, {"released_at": None, **row})

    def update_window(self, window_id, fields):
        self.w[window_id].update(fields)
        return dict(self.w[window_id])

    def grants(self, window_ids):
        return [dict(g) for g in self.g.values() if g["window_id"] in set(window_ids)]

    def grants_of(self, student_id):
        return [dict(g) for g in self.g.values() if g["student_id"] == student_id]

    def add_grant(self, row):
        return self._new(self.g, row)

    def starts(self, window_ids=None, user_id=None):
        return [dict(s) for s in self.s.values() if (window_ids is None or s["window_id"] in set(window_ids))
                and (user_id is None or s["user_id"] == user_id)]

    def start(self, start_id):
        return dict(self.s[start_id]) if start_id in self.s else None

    def start_with_attempt(self, attempt_id):
        return next((dict(s) for s in self.s.values() if attempt_id in s["attempt_ids"]), None)

    def add_start(self, row):
        if any(s["window_id"] == row["window_id"] and s["user_id"] == row["user_id"] and s.get("grant_id") == row.get("grant_id")
               for s in self.s.values()):
            raise ClassConflict("duplicate")
        return self._new(self.s, {"sitting_id": None, **row})

    def update_start(self, start_id, fields):
        self.s[start_id].update(fields)
        return dict(self.s[start_id])


def at(minutes):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def png():
    out = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(out, "PNG")
    return out.getvalue()


@pytest.fixture
def school(answer_store, monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_API_KEY", raising=False)
    app = create_app(auth=SchoolAuth())
    app.state.answers = answer_store
    app.state.quiz_modes = modes = MemoryQuizModes()
    return app, modes


def client(app, token):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             headers={"Authorization": f"Bearer {token}"})


async def final_attempts(c, start_id):
    ids = []
    for i, _ in enumerate(T["quiz"]["questions"]):
        r = await c.post("/api/math/quiz-attempts", json={"unit": "t", "index": i, "new": True, "start_id": start_id,
                                                         "question_version": question_version(quiz_snapshot(T, i))})
        assert r.status_code == 200, r.text
        ids.append(r.json()["attempt"]["id"])
    return ids


async def photograph(c, aid):
    scan = await c.post(f"/api/math/answer-attempts/{aid}/scans", json={"renew": True, "direct": True})
    if scan.status_code != 200:
        return scan
    sid = scan.json()["scan"]["id"]
    await c.post(f"/api/math/answer-scans/{sid}/confirm")
    lease = (await c.post(f"/api/math/answer-scans/{sid}/uploads", json={"key": str(uuid.uuid4())})).json()
    return await c.post(f"/api/math/answer-scans/{sid}/uploads/{lease['lease_id']}", files={"photo": ("a.png", png(), "image/png")})


def test_only_the_class_teacher_opens_a_final_window_for_a_quiz_unit_of_the_class(school):
    app, modes = school

    async def run():
        async with client(app, TEACHER) as teacher, client(app, OTHER_TEACHER) as other, client(app, OWNER) as student:
            good = {"unit_id": "t", "opens_at": at(-5), "closes_at": at(90)}
            assert (await other.post("/api/classes/1/quiz-windows", json=good)).status_code == 403
            assert (await student.post("/api/classes/1/quiz-windows", json=good)).status_code == 403
            assert (await teacher.post("/api/classes/1/quiz-windows", json={**good, "unit_id": "k"})).status_code == 400   # not a unit of the class
            assert (await teacher.post("/api/classes/1/quiz-windows", json={**good, "closes_at": at(-6)})).status_code == 400
            assert (await teacher.post("/api/classes/1/quiz-windows", json={**good, "closes_at": at(20)})).status_code == 400  # shorter than 45 min
            made = await teacher.post("/api/classes/1/quiz-windows", json=good)
            assert made.status_code == 201 and made.json()["unit_id"] == "t"
            again = await teacher.post("/api/classes/1/quiz-windows", json=good)
            assert (again.status_code, again.json()["detail"]) == (409, "window_already_open")
            listed = (await teacher.get("/api/classes/1/quiz-windows")).json()
            assert [w["id"] for w in listed["windows"]] == [made.json()["id"]]
    asyncio.run(run())


def test_a_final_sitting_starts_once_on_the_servers_clock_and_is_handed_in_once(school):
    app, modes = school

    async def run():
        async with client(app, TEACHER) as teacher, client(app, OWNER) as student:
            later = (await teacher.post("/api/classes/1/quiz-windows",
                                        json={"unit_id": "t2", "opens_at": at(60), "closes_at": at(180)})).json()
            early = await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t2"})
            assert (early.status_code, early.json()["detail"]) == (409, "final_not_open")   # before the window
            offers = (await student.get("/api/math/quiz-windows")).json()["offers"]
            assert offers == []
            window = (await teacher.post("/api/classes/1/quiz-windows",
                                         json={"unit_id": "t", "opens_at": at(-5), "closes_at": at(30 + 60)})).json()
            started = await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})
            assert started.status_code == 201
            start = started.json()["start"]
            began = datetime.fromisoformat(start["started_at"])
            assert datetime.fromisoformat(start["deadline"]) == began + timedelta(minutes=45 + 10)
            resumed = (await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})).json()["start"]
            assert resumed["id"] == start["id"] and resumed["started_at"] == start["started_at"]   # a reload keeps the clock
            # practice of the unit is closed while its final waits
            blocked = await student.post("/api/math/quiz-attempts", json={
                "unit": "t", "index": 0, "new": True, "first": True, "question_version": question_version(quiz_snapshot(T, 0))})
            assert (blocked.status_code, blocked.json()["detail"]) == (409, "final_open")
            ids = await final_attempts(student, start["id"])
            assert modes.start(start["id"])["attempt_ids"] == ids
            assert (await photograph(student, ids[0])).status_code == 200
            handed = await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "start_id": start["id"],
                                                                           "client_key": str(uuid.uuid4())})
            assert handed.status_code == 200, handed.text
            sitting = handed.json()
            assert sitting["mode"] == "final" and sitting["window_id"] == window["id"]
            assert sitting["released"] is False and sitting["grade"] is None   # results wait for the teacher
            assert modes.start(start["id"])["sitting_id"] == sitting["id"]
            twice = await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})
            assert (twice.status_code, twice.json()["detail"]) == (409, "final_already_handed_in")
            # after hand-in, practice is open again
            practice = await student.post("/api/math/quiz-attempts", json={
                "unit": "t", "index": 0, "new": True, "first": True, "question_version": question_version(quiz_snapshot(T, 0))})
            assert practice.status_code == 200
            # the answer's check is hidden too
            answer = (await student.get(f"/api/math/answer-attempts/{ids[0]}")).json()
            assert answer["unreleased"] is True and answer["effective_score"] is None
            # the teacher releases: the student sees the sitting as it is
            released = await teacher.post(f"/api/classes/1/quiz-windows/{window['id']}/release")
            assert released.status_code == 200 and released.json()["released_at"]
            mine = (await student.get("/api/math/quiz-sittings?unit_id=t")).json()["sittings"]
            assert mine[0]["released"] is True and mine[0]["questions"][1]["state"] == "missing"
            assert "unreleased" not in (await student.get(f"/api/math/answer-attempts/{ids[0]}")).json()
    asyncio.run(run())


def test_a_photo_after_the_deadline_is_refused_and_the_sitting_is_handed_in(school):
    app, modes = school

    async def run():
        async with client(app, TEACHER) as teacher, client(app, OWNER) as student:
            await teacher.post("/api/classes/1/quiz-windows", json={"unit_id": "t", "opens_at": at(-5), "closes_at": at(90)})
            start = (await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})).json()["start"]
            ids = await final_attempts(student, start["id"])
            assert (await photograph(student, ids[0])).status_code == 200
            modes.s[start["id"]]["deadline"] = at(-1)   # the time ran out
            late = await photograph(student, ids[1])
            assert (late.status_code, late.json()["detail"]) == (409, "quiz_time_over")
            sid = modes.start(start["id"])["sitting_id"]
            assert sid   # handed in by the server, with what it had
            mine = (await student.get("/api/math/quiz-sittings?unit_id=t")).json()["sittings"]
            assert mine[0]["id"] == sid and mine[0]["mode"] == "final" and mine[0]["time_up"] is True
            more = await student.post("/api/math/quiz-attempts", json={
                "unit": "t", "index": 1, "new": True, "start_id": start["id"], "question_version": question_version(quiz_snapshot(T, 1))})
            assert (more.status_code, more.json()["detail"]) == (409, "quiz_time_over")
            # the page's own hand-in afterwards is the same sitting
            again = await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "start_id": start["id"]})
            assert again.json()["id"] == sid
    asyncio.run(run())


def test_the_teacher_grants_another_final_sitting_and_the_latest_final_is_the_official_grade(school):
    app, modes = school

    async def run():
        async with client(app, TEACHER) as teacher, client(app, OWNER) as student, client(app, OTHER) as classmate:
            window = (await teacher.post("/api/classes/1/quiz-windows",
                                         json={"unit_id": "t", "opens_at": at(-5), "closes_at": at(90)})).json()
            start = (await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})).json()["start"]
            ids = await final_attempts(student, start["id"])
            first = (await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "start_id": start["id"]})).json()
            await teacher.post(f"/api/classes/1/quiz-windows/{window['id']}/close")
            bad = await teacher.post(f"/api/classes/1/quiz-windows/{window['id']}/grants",
                                     json={"student_email": "nobody@x.test", "until": at(60 * 24)})
            assert bad.status_code == 400
            long = await teacher.post(f"/api/classes/1/quiz-windows/{window['id']}/grants",
                                      json={"student_email": EMAILS[OWNER], "until": at(60 * 24), "reason": "x" * 201})
            assert long.status_code == 400
            granted = await teacher.post(f"/api/classes/1/quiz-windows/{window['id']}/grants",
                                         json={"student_email": EMAILS[OWNER], "until": at(60 * 24), "reason": "נעדר/ה"})
            assert granted.status_code == 201 and granted.json()["reason"] == "נעדר/ה"
            assert (await classmate.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})).status_code == 409  # window closed
            second = await student.post("/api/math/quiz-sittings/start", json={"unit_id": "t"})
            assert second.status_code == 201 and second.json()["start"]["grant_id"] == granted.json()["id"]
            ids2 = await final_attempts(student, second.json()["start"]["id"])
            last = (await student.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids2,
                                                                         "start_id": second.json()["start"]["id"]})).json()
            mine = (await student.get("/api/math/quiz-sittings?unit_id=t")).json()["sittings"]
            assert official_grades(mine)["t"]["id"] == last["id"] != first["id"]
    asyncio.run(run())


def test_official_grade_ignores_practice_and_deadline_is_cut_at_the_window_end():
    views = [{"unit_id": "t", "mode": "final", "submitted_at": "2026-11-01T10:00:00Z", "id": "f1"},
             {"unit_id": "t", "mode": "practice", "submitted_at": "2026-11-02T10:00:00Z", "id": "p1"},
             {"unit_id": "k", "mode": "practice", "submitted_at": "2026-11-02T10:00:00Z", "id": "p2"}]
    assert {u: v["id"] for u, v in official_grades(views).items()} == {"t": "f1"}
    started = datetime(2026, 11, 6, 8, 0, tzinfo=timezone.utc)
    assert deadline_for(T, started, started + timedelta(hours=3)) == started + timedelta(minutes=55)
    assert deadline_for(T, started, started + timedelta(minutes=30)) == started + timedelta(minutes=30)


def test_without_the_tables_final_routes_are_unavailable_and_practice_works(answer_store, monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    app = create_app(auth=SchoolAuth())
    app.state.answers = answer_store

    async def run():
        async with client(app, TEACHER) as teacher, client(app, OWNER) as student:
            r = await teacher.get("/api/classes/1/quiz-windows")
            assert (r.status_code, r.json()["detail"]) == (503, "quiz_modes_unavailable")
            practice = await student.post("/api/math/quiz-attempts", json={
                "unit": "t", "index": 0, "new": True, "first": True, "question_version": question_version(quiz_snapshot(T, 0))})
            assert practice.status_code == 200
    asyncio.run(run())


def test_the_migration_keeps_old_sittings_as_practice(answer_store):
    with answer_store.connect() as c:
        modes = c.execute("select column_default from information_schema.columns "
                          "where table_name='math_quiz_sittings' and column_name='mode'").fetchone()[0]
        assert "practice" in modes
        assert c.execute("select to_regclass('public.math_quiz_starts') is not null").fetchone()[0]


# ---- in a browser: the student's final quiz, and its result before and after the teacher releases it
playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def final_server(answer_store, monkeypatch):
    import socket
    import threading
    import time
    import uvicorn
    from app.answer_grading import validate_assessment
    from test_answer_grading import assessment
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    class Auth(SchoolAuth):
        developers = frozenset({EMAILS[OWNER]})   # checks straight with the (fake) AI, like the quiz tests

    app = create_app(auth=Auth())
    app.state.answers = answer_store
    app.state.quiz_modes = modes = MemoryQuizModes()
    calls = []

    class Grader:
        def grade(self, image, snapshot):
            calls.append(snapshot["name"])
            return validate_assessment(assessment(score=100))
    app.state.answer_grader = Grader()
    window = modes.add_window({"class_id": 1, "unit_id": "t", "opens_at": at(-5), "closes_at": at(120)})
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", modes, window, calls
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def test_a_student_takes_the_final_quiz_once_and_sees_the_grade_after_release(final_server, tmp_path):
    import re
    from test_unit_quiz import photograph, signed_in
    url, modes, window, calls = final_server
    with playwright.sync_playwright() as p:
        browser, page, errors = signed_in(p, url)
        try:
            step = page.locator('.mx-uquiz[data-uquiz="t"]')
            playwright.expect(step).to_have_attribute("aria-label", re.compile("בוחן מסכם פתוח"))
            step.click()
            sheet = page.locator(".mx-uq-sheet")
            playwright.expect(sheet.locator(".mx-uq-final")).to_contain_text("פעם אחת")
            playwright.expect(sheet.locator("[data-act=uq-start]")).to_have_count(0)   # no practice while the final waits
            sheet.locator("[data-act=uq-final]").click()
            playwright.expect(sheet.locator("[role=alert]")).to_contain_text("פעם אחת בלבד")
            assert not modes.s   # nothing started before the confirmation
            sheet.locator("[data-act=uq-final-go]").click()
            paper = page.locator(".mx-uq-paper")
            playwright.expect(paper.locator("h3")).to_have_text("בוחן מסכם")
            playwright.expect(paper.locator(".mx-uq-clock")).to_have_text(re.compile(r"^4[45]:\d\d$"))
            assert len(modes.s) == 1
            photograph(page, 0, tmp_path)
            page.reload()   # the server's clock and answers carry on
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            playwright.expect(page.locator(".mx-uq-paper h3")).to_have_text("בוחן מסכם")
            playwright.expect(page.locator('[data-uq-i="0"] [role=status]')).to_have_text("✓ התשובה נשמרה")
            paper.locator("[data-act=uq-submit]").click()
            paper.locator("[data-act=uq-submit]").click()   # the others are left without an answer
            playwright.expect(sheet.locator("h3")).to_have_text("בוחן מסכם: הוגש", timeout=20000)
            playwright.expect(sheet.locator(".mx-uq-report")).to_contain_text("התוצאות יפורסמו על ידי המורה")
            playwright.expect(sheet.locator(".mx-uq-verdict")).to_have_count(0)
            # released: the result shows the grade (25 for the one answer)
            modes.update_window(window["id"], {"released_at": at(0)})
            page.reload()
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            playwright.expect(sheet.locator("[data-act=uq-start]")).to_have_text("ניסיון נוסף")   # practice is open again
            sheet.locator("[data-uq-result]").first.click()
            playwright.expect(sheet.locator("h3")).to_have_text("בוחן מסכם: 25/100", timeout=20000)
            assert not errors, errors
        finally:
            browser.close()
