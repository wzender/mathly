"""The student's task list (GET /api/math/my-tasks): their assignments, focus practice given to them only, the final
quizzes open to them, and a worksheet returned for a fix; nobody else's."""
import asyncio
from datetime import datetime, timedelta, timezone

from app.main import create_app
from test_assignments import STUDENT, TEACHER, MemoryAssignments, Sittings, client
from test_assignments import FocusAuth, CLASSMATE
from test_quiz_modes import MemoryQuizModes
from test_worksheets import MemoryWorksheets, photos, upload


def at(minutes):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat()


def make_app():
    app = create_app(auth=FocusAuth())
    app.state.assignments, app.state.answers = MemoryAssignments(), Sittings()
    app.state.worksheets, app.state.quiz_modes = MemoryWorksheets(), MemoryQuizModes()
    return app


def test_the_task_list_holds_the_students_assignments_finals_and_returned_work():
    app = make_app()
    app.state.quiz_modes.add_window({"class_id": 3, "unit_id": "t", "opens_at": at(-5), "closes_at": at(120)})

    async def check():
        async with client(app, TEACHER) as teacher, client(app, STUDENT) as student, client(app, CLASSMATE) as classmate:
            wid = (await upload(teacher)).json()["id"]
            await teacher.post("/api/classes/3/assignments", json={"title": "ש״ב", "due_on": "2026-11-12",
                                                                    "items": [{"kind": "worksheet", "id": wid}]})
            await teacher.post("/api/classes/3/assignments", json={"title": "חיזוק", "due_on": "2026-11-15",
                                                                    "items": [{"kind": "skill", "id": "t_ext"}],
                                                                    "student_emails": ["classmate@x.test"]})
            sub = (await student.put(f"/api/math/worksheets/{wid}/submission", files=photos(1))).json()
            await teacher.post(f"/api/classes/3/worksheets/{wid}/submissions/{sub['id']}/return", json={"comment": "לתקן"})
            mine = (await student.get("/api/math/my-tasks")).json()
            assert [a["title"] for a in mine["assignments"]["assignments"]] == ["ש״ב"]   # not the classmate's focus practice
            (returned,) = mine["assignments"]["submissions"]
            assert (returned["state"], returned["return_comment"]) == ("returned", "לתקן")
            (final,) = mine["finals"]
            assert final["window"]["unit_id"] == "t" and final["start"] is None
            theirs = (await classmate.get("/api/math/my-tasks?student_id=" + STUDENT)).json()   # an id is not taken
            assert [a["title"] for a in theirs["assignments"]["assignments"]] == ["חיזוק", "ש״ב"]
            assert theirs["assignments"]["submissions"] == []
    asyncio.run(check())


def test_parts_that_cannot_be_read_are_none_and_signing_in_is_required():
    app = make_app()
    app.state.assignments = MemoryAssignments(fail=True)

    class NoFinals(MemoryQuizModes):
        def windows(self, class_ids):
            from app.quiz_modes import QuizModesUnavailable
            raise QuizModesUnavailable("quiz_modes_unavailable")
    app.state.quiz_modes = NoFinals()

    async def check():
        async with client(app, STUDENT) as student:
            got = (await student.get("/api/math/my-tasks")).json()
            assert got == {"assignments": None, "finals": None}
        async with client(app, "nobody") as nobody:
            assert (await nobody.get("/api/math/my-tasks")).status_code == 401
    asyncio.run(check())


# ---- in a browser: the home summary and the list, nearest first, one state each
import pytest  # noqa: E402

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def task_server():
    import socket
    import threading
    import time
    import uvicorn
    app = make_app()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", app
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def test_the_student_sees_one_list_of_owed_work_nearest_first(task_server):
    import httpx
    from test_focus_browser import session
    url, app = task_server
    app.state.quiz_modes.add_window({"class_id": 3, "unit_id": "t", "opens_at": at(-5), "closes_at": at(120)})
    app.state.assignments.add({"class_id": 3, "title": "חזרה", "note": "", "due_on": "2099-11-20",
                               "items": [{"kind": "skill", "id": "t_ext"}], "student_emails": None})
    with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {TEACHER}"}) as teacher, \
            httpx.Client(base_url=url, headers={"Authorization": f"Bearer {STUDENT}"}) as student:
        wid = teacher.post("/api/classes/3/worksheets", data={"title": "דף"}, files=photos(1)).json()["id"]
        teacher.post("/api/classes/3/assignments", json={"title": "ש״ב", "due_on": "2099-11-12", "items": [{"kind": "worksheet", "id": wid}]})
        sub = student.put(f"/api/math/worksheets/{wid}/submission", files=photos(1)).json()
        teacher.post(f"/api/classes/3/worksheets/{wid}/submissions/{sub['id']}/return", json={"comment": "לתקן את 2", "due_on": "2099-11-14"})
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, STUDENT)
            page.goto(url)
            page.locator('.mx-nav [data-view="home"]').click()
            summary = page.locator(".mx-tasks-sum")
            playwright.expect(summary).to_contain_text("3 משימות פתוחות")
            playwright.expect(summary).to_contain_text("הקרובה: בוחן מסכם: טכניקה אלגברית 1")
            summary.click()
            rows = page.locator(".mx-tasks-sheet .mx-task")
            playwright.expect(rows).to_have_count(3)
            playwright.expect(rows.locator("b")).to_have_text(["בוחן מסכם: טכניקה אלגברית 1", "ש״ב", "חזרה"])
            playwright.expect(rows.locator(".mx-task-chip")).to_have_text(["עוד לא התחיל", "הוחזר לתיקון", "עוד לא התחיל"])
            playwright.expect(rows.nth(1)).to_contain_text("לתקן את 2")
            rows.nth(1).locator("[data-ws-open]").click()   # opens the returned worksheet to fix it
            playwright.expect(page.locator(".mx-ws-sheet .mx-ws-returned")).to_be_visible()
            # nothing owed: the list says so and offers the way on
            page.route("**/api/math/my-tasks", lambda route: route.fulfill(json={
                "assignments": {"assignments": [], "sittings": [], "worksheets": [], "submissions": [], "today": "2026-11-06"}, "finals": []}))
            page.locator(".mx-ws-sheet .mx-x").click()
            page.locator(".mx-tasks-sum").click()
            playwright.expect(page.locator(".mx-tasks-sheet [role=status]")).to_contain_text("אין מה להגיש עכשיו")
            playwright.expect(page.locator('.mx-tasks-sheet .mx-btn[data-act="grades"]')).to_be_visible()
            assert not errors, errors
        finally:
            browser.close()


def test_the_grades_page_labels_each_grade_and_opens_its_result(task_server):
    from test_focus_browser import session
    url, app = task_server
    q = lambda earned, skills=("t_ext",): {"points": 25, "earned": earned, "state": "checked" if earned is not None else "waiting", "skills": list(skills)}
    final = {"id": "f1", "unit_id": "t", "mode": "final", "released": True, "grade": 62, "open": 0, "window_id": "w",
             "submitted_at": "2026-11-05T09:00:00Z", "time_up": False, "attempts": ["a1", "a2", "a3", "a4"],
             "questions": [q(25), q(12), q(25), q(0)]}
    best = {**final, "id": "p1", "mode": "practice", "grade": 85, "submitted_at": "2026-11-02T09:00:00Z", "attempts": ["b1", "b2", "b3", "b4"]}
    waiting = {**final, "id": "p2", "mode": "practice", "grade": None, "open": 1, "submitted_at": "2026-11-04T09:00:00Z",
               "attempts": ["c1", "c2", "c3", "c4"], "questions": [q(25), q(None), q(25), q(25)]}
    data = {"units": [{"unit_id": "t", "name": "טכניקה אלגברית 1", "official": final, "practice_best": best,
                       "practice_latest": waiting, "sittings": [final, waiting, best]}],
            "quizzes_known": True, "comments": [{"attempt_id": "a2", "question": "בוחן מסכם · שאלה 2", "score": 50, "question_id": "quiz:t:1"}],
            "worksheets": [{"id": "s1", "worksheet_id": "w1", "title": "דף פילוג", "assignment": "חזרה", "unit_id": "t",
                            "checked_at": "2026-11-05T09:00:00Z", "score": 90, "comment": "יפה", "state": "checked"}]}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, STUDENT)
            page.route("**/api/math/my-grades", lambda route: route.fulfill(json=data))
            page.route("**/api/math/quiz-sittings?unit_id=t", lambda route: route.fulfill(json={"sittings": [final, waiting, best]}))
            page.goto(url)
            page.locator('.mx-nav [data-view="home"]').click()
            page.locator('.mx-nav [data-view="grades"]').click()
            g = page.locator(".mx-grades-page")
            playwright.expect(g.locator(".mx-glist-new")).to_contain_text("הערה חדשה מהמורה")
            playwright.expect(g.locator(".mx-glist-units")).to_contain_text("טכניקה אלגברית 1 62")   # the unit's grade, on one line
            rows = g.locator(".mx-glist-row")
            playwright.expect(rows).to_have_count(4)   # one row each, newest first
            playwright.expect(rows.nth(0)).to_contain_text("בוחן מסכם")
            playwright.expect(rows.nth(0)).to_contain_text("62/100")
            playwright.expect(rows.nth(0)).to_contain_text("★ ציון היחידה")
            playwright.expect(rows.nth(0)).to_contain_text("💬")                    # the new comment is on the final
            playwright.expect(rows.nth(1)).to_contain_text("שיעורי בית")
            playwright.expect(rows.nth(1)).to_contain_text("90/100")
            playwright.expect(rows.nth(1).locator("[data-ws-open]")).to_have_text("צפייה")
            playwright.expect(rows.nth(2)).to_contain_text("ממתין לבדיקה · שאלה אחת")
            playwright.expect(rows.nth(2).locator('[data-uquiz="t"]')).to_have_text("הגשה מחדש")   # a בוחן חיזוק: again
            playwright.expect(rows.nth(3)).to_contain_text("85/100")
            playwright.expect(rows.nth(3)).to_contain_text("הכי טוב")
            playwright.expect(rows.nth(0).locator("[data-uquiz]")).to_have_count(0)   # a בוחן מסכם is handed in once
            rows.nth(0).locator('[data-grade-sitting="t:f1"]').click()
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן מסכם: 62/100", timeout=10000)
            assert page.evaluate("""() => { const k = Object.keys(localStorage).find(k => k.startsWith('mathly.progress.v1:'));
                return JSON.parse(localStorage.getItem(k)).uq.t.history.some(h => h.sid === 'f1' && h.mode === 'final'); }""")
            assert not errors, errors
        finally:
            browser.close()


def test_homework_not_handed_in_yet_is_first_in_the_grades_with_a_hand_in_button(task_server):
    import httpx
    from test_focus_browser import session
    url, app = task_server
    with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {TEACHER}"}) as teacher:
        wid = teacher.post("/api/classes/3/worksheets", data={"title": "דף"}, files=photos(1)).json()["id"]
        teacher.post("/api/classes/3/assignments", json={"title": "ש״ב", "due_on": "2099-11-12", "items": [{"kind": "worksheet", "id": wid}]})
    empty = {"units": [], "quizzes_known": True, "comments": [], "worksheets": []}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, STUDENT)
            page.route("**/api/math/my-grades", lambda route: route.fulfill(json=empty))
            page.goto(url)
            page.locator('.mx-nav [data-view="home"]').click()
            playwright.expect(page.locator(".mx-asgs")).to_be_visible()   # the assignments are known
            page.locator('.mx-nav [data-view="grades"]').click()
            row = page.locator(".mx-grades-page .mx-glist-row.todo")
            playwright.expect(row).to_contain_text("שיעורי בית")
            playwright.expect(row).to_contain_text("עד 12.11")
            row.locator("[data-ws-open]").click()
            playwright.expect(page.locator(".mx-ws-sheet")).to_be_visible()
            assert not errors, errors
        finally:
            browser.close()
