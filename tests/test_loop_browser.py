"""The whole loop, end to end, in two browsers: the teacher opens a final quiz, the student sits it, the teacher sends
the class's answers to the AI in one batch, reviews the answer the AI could not read from the inbox and releases the
results; the student sees the grade on the grades page and the teacher sees the skills to work on."""
import re
import socket
import threading
import time
import uuid
from datetime import datetime, timedelta

import pytest
import uvicorn

from app.answer_grading import validate_assessment
from app.main import create_app
from scan_support import OTHER, OWNER, answer_store, postgres_server  # noqa: F401
from test_ai_batches import BudgetAuth, MemoryBudget
from test_ai_queue import MemoryQueue, mail
from test_answer_grading import assessment
from test_quiz_modes import MemoryQuizModes
from test_unit_quiz import photograph

playwright = pytest.importorskip("playwright.sync_api")


class LoopAuth(BudgetAuth):
    def user_accounts(self, emails):
        return {mail(OWNER): {"id": OWNER, "name": "Dana"}} if mail(OWNER) in emails else {}

    def _admin(self, path, *args, **kwargs):
        if path.startswith("/rest/v1/math_progress"):
            return []
        return super()._admin(path, *args, **kwargs)


@pytest.fixture
def loop_server(answer_store, monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    app = create_app(auth=LoopAuth())
    app.state.answers, app.state.ai_queue = answer_store, MemoryQueue()
    app.state.class_budget, app.state.quiz_modes = MemoryBudget(), MemoryQuizModes()
    calls = []

    class Grader:
        def grade(self, image, snapshot):
            calls.append(snapshot["name"])
            if snapshot["name"].endswith("2"):   # question 2's photo cannot be read
                return validate_assessment(assessment(score=0, readable=False))
            return validate_assessment(assessment(score=100))
    app.state.answer_grader = Grader()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", app, calls
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def page_of(browser, url, owner, errors):
    from test_answer_browser import session
    page = session(browser, owner=owner).new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept())
    page.goto(url)
    page.locator('.mx-nav [data-view="home"]').wait_for()
    tab = page.locator('.mx-nav [data-view="path"]')   # a student's trail; a class teacher has only home
    (tab if tab.count() else page.locator('.mx-nav [data-view="home"]')).click()
    return page


def report_tab(teacher, tab):
    teacher.locator('[data-act="class-report"]').first.click()
    sheet = teacher.locator(".mx-report-sheet")
    sheet.locator(f"[data-report-tab={tab}]").click()
    return sheet


def test_final_quiz_from_opening_to_the_students_grade_and_the_teachers_focus_list(loop_server, tmp_path):
    url, app, calls = loop_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        errors = []
        try:
            # ---- the teacher opens the final quiz of unit t, from a few minutes ago
            teacher = page_of(browser, url, OTHER, errors)
            sheet = report_tab(teacher, "finals")
            form = sheet.locator("[data-final-open]")
            form.locator("[name=opens]").fill((datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M"))
            form.locator("[name=closes]").fill((datetime.now() + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"))
            form.locator("button[type=submit]").click()
            playwright.expect(sheet.locator(".mx-final-t")).to_contain_text("פתוח")

            # ---- the student sits it: two answers photographed
            student = page_of(browser, url, OWNER, errors)
            student.locator('.mx-uquiz[data-uquiz="t"]').click()
            student.locator("[data-act=uq-final]").click()
            student.locator("[data-act=uq-final-go]").click()
            playwright.expect(student.locator(".mx-uq-paper h3")).to_have_text("בוחן מסכם")
            photograph(student, 0, tmp_path)
            photograph(student, 1, tmp_path)
            paper = student.locator(".mx-uq-paper")
            paper.locator("[data-act=uq-submit]").click()
            paper.locator("[data-act=uq-submit]").click()
            playwright.expect(student.locator(".mx-uq-sheet h3")).to_have_text("בוחן מסכם: הוגש", timeout=15000)
            assert not calls   # a student's answers wait for the teacher

            # ---- the teacher sends the whole quiz in one batch, from the class's budget
            teacher.reload()
            teacher.locator('.mx-nav [data-view="home"]').click()
            sheet = report_tab(teacher, "finals")
            card = sheet.locator(".mx-final-t")
            playwright.expect(card).to_contain_text("הגישו 1 מתוך 1")
            card.locator("[data-batch]").click()
            playwright.expect(sheet.locator(".mx-flash")).to_contain_text("נשלחו 2 בדיקות")
            deadline = time.monotonic() + 15   # the batch runs after the answer: wait for both checks
            while (len(calls) < 2 or any(r["state"] == "sending" for r in app.state.ai_queue.rows)) and time.monotonic() < deadline:
                time.sleep(.1)
            assert len(calls) == 2 and app.state.class_budget.used[1] == 1   # the unreadable photo was given back

            # ---- the inbox: the unreadable answer, reviewed by the teacher
            teacher.reload()
            teacher.locator('.mx-nav [data-view="home"]').click()
            sheet = report_tab(teacher, "inbox")
            sheet.locator('[data-inbox-filter="state"]').select_option("unreadable")
            rows = sheet.locator(".mx-inbox-row")
            playwright.expect(rows).to_have_count(1)
            rows.locator("[data-inbox-open]").click()
            review = teacher.locator(".mx-tr-sheet")
            review.locator("[name=score]").fill("60")
            review.locator("[data-review-form] [type=submit]").click()
            playwright.expect(teacher.locator(".mx-report-sheet .mx-report")).to_contain_text("סיימתם את כל מה שממתין")

            # ---- released: 25 (question 1) + 15 (60% of question 2) = 40
            sheet.locator("[data-report-tab=finals]").click()
            sheet.locator("[data-final-release]").click()
            playwright.expect(sheet.locator(".mx-final-t")).to_contain_text("התוצאות פורסמו")
            student.reload()
            student.locator('.mx-nav [data-view="home"]').click()
            student.locator('.mx-nav [data-view="grades"]').click()
            playwright.expect(student.locator(".mx-grades-page .mx-glist-row").first).to_contain_text("40/100", timeout=10000)

            # ---- the teacher sees what Dana should work on: the skills of the points she lost
            sheet.locator("[data-report-tab=list]").click()
            dana = sheet.locator(".mx-report-student").first
            dana.locator("summary").first.click()
            playwright.expect(dana.locator(".mx-focus .mx-focus-list li").first).to_contain_text(re.compile("איבד \\d+ נק׳ בבחנים"))
            assert not errors, errors
        finally:
            browser.close()


def test_worksheet_from_phone_hand_in_to_return_resubmit_and_check(tmp_path):
    """A worksheet: handed in from the phone with a note, returned for a fix, handed in again, checked from the inbox;
    the student's card and the teacher's report then say the same."""
    import json
    import httpx
    from test_worksheets_browser import NoAnswers, SchoolAuth, STUDENT, TEACHER, open_tasks, photo_file, session
    from test_assignments import MemoryAssignments
    from test_worksheets import MemoryWorksheets
    app = create_app(auth=SchoolAuth())
    app.state.assignments, app.state.worksheets, app.state.answers = MemoryAssignments(), MemoryWorksheets(), NoAnswers()
    store = app.state.worksheets
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        while not server.started:
            time.sleep(.01)
        url = f"http://127.0.0.1:{sock.getsockname()[1]}"
        try:
            with httpx.Client(base_url=url, headers={"Authorization": f"Bearer {TEACHER}"}) as api:
                wid = api.post("/api/classes/3/worksheets", data={"title": "דף פילוג"},
                               files=[("files", ("a.jpg", open(photo_file(tmp_path, "s.jpg", "white"), "rb").read(), "image/jpeg"))]).json()["id"]
                api.post("/api/classes/3/assignments", json={"title": "שיעורי בית", "due_on": "2099-01-01", "items": [{"kind": "worksheet", "id": wid}]})
            page_jpg = open(photo_file(tmp_path, "phone.jpg", "purple"), "rb").read()
            aid, sid = str(uuid.uuid4()), str(uuid.uuid4())
            polls = {"n": 0}

            def poll(route):
                polls["n"] += 1
                done = polls["n"] >= 2
                route.fulfill(json={"attempt": {"id": aid}, "scan": {"id": sid, "state": "received" if done else "waiting", "code": "1234"},
                                    "attachment": {"id": "x"} if done else None})
            with playwright.sync_playwright() as p:
                browser = p.chromium.launch()
                try:
                    # ---- the student, on a computer, takes the page with the phone and sends it with a note
                    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                    ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
                    ctx.add_init_script('''window.supabase={createClient:()=>({auth:{
                      getSession:async()=>({data:{session:{access_token:"%s",user:{id:"%s"}}}}),
                      onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),signOut:async()=>{}}})};''' % (STUDENT, STUDENT))
                    student = ctx.new_page()
                    s_errors = []
                    student.on("pageerror", lambda e: s_errors.append(str(e)))
                    student.route("**/api/me", lambda route: route.fulfill(json={**route.fetch().json(), "answer_scans": True}))
                    student.route("**/api/math/worksheet-attempts", lambda route: route.fulfill(json={"attempt": {"id": aid}, "scan": None, "attachment": None}))
                    student.route(f"**/api/math/answer-attempts/{aid}/scans", lambda route: route.fulfill(json={"attempt": {"id": aid}, "scan": {"id": sid, "state": "waiting", "code": "1234"}}))
                    student.route(f"**/api/math/answer-attempts/{aid}/image", lambda route: route.fulfill(body=page_jpg, content_type="image/jpeg"))
                    student.route(f"**/api/math/answer-attempts/{aid}", poll)
                    student.goto(url)
                    student.locator('.mx-nav [data-view="home"]').click()
                    student.locator(".mx-asgs [data-asg-go]").click()
                    ws = student.locator(".mx-ws-sheet")
                    ws.locator("[data-ws-phone]").click()
                    playwright.expect(ws.locator(".mx-ws-chosen li")).to_have_count(1, timeout=10000)
                    ws.locator("[data-ws-note]").fill("לא הבנתי את 3")
                    ws.locator("[data-ws-send]").click()
                    playwright.expect(ws).to_contain_text("ממתין לבדיקה")

                    # ---- the teacher returns it
                    teacher, t_errors = session(browser, TEACHER)
                    sheet = open_tasks(teacher, url)
                    sheet.locator("[data-report-tab=inbox]").click()
                    sheet.locator("[data-inbox-open]").click()
                    review = sheet.locator(".mx-ws-review")
                    playwright.expect(review.locator(".mx-ws-note-shown")).to_contain_text("לא הבנתי את 3")
                    review.locator(".mx-ws-return-box summary").click()
                    review.locator("[data-ws-return] [name=comment]").fill("חסרה דרך פתרון")
                    review.locator("[data-ws-return] button[type=submit]").click()
                    playwright.expect(sheet.locator(".mx-report")).to_contain_text("אין מה לבדוק")

                    # ---- the student fixes it
                    student.unroute(f"**/api/math/answer-attempts/{aid}")
                    student.reload()
                    student.locator('.mx-nav [data-view="home"]').click()
                    student.locator(".mx-tasks-sum").click()
                    playwright.expect(student.locator(".mx-tasks-sheet .mx-task-chip")).to_have_text("הוחזר לתיקון")
                    student.locator(".mx-tasks-sheet [data-ws-open]").click()
                    ws.locator("[data-ws-file]").set_input_files([photo_file(tmp_path, "fix.jpg", "green")])
                    ws.locator("[data-ws-send]").click()
                    playwright.expect(ws).to_contain_text("גרסה 2")

                    # ---- the teacher checks the new version from the inbox
                    sheet = open_tasks(teacher, url)
                    sheet.locator("[data-report-tab=inbox]").click()
                    playwright.expect(sheet.locator(".mx-inbox-row")).to_contain_text("מתוקן")
                    sheet.locator("[data-inbox-open]").click()
                    sheet.locator("[data-ws-check] [name=score]").fill("90")
                    sheet.locator("[data-ws-check] button[type=submit]").click()
                    playwright.expect(sheet.locator(".mx-report")).to_contain_text("סיימתם את כל מה שממתין")
                    sheet.locator("[data-report-tab=tasks]").click()
                    sheet.locator(".mx-asg-who summary").click()
                    playwright.expect(sheet.locator(".mx-task-state")).to_have_text("נבדק")

                    # ---- the student sees the same
                    student.reload()
                    student.locator('.mx-nav [data-view="home"]').click()
                    playwright.expect(student.locator(".mx-asg-done summary")).to_have_text("הושלמו (1)")
                    student.locator(".mx-asg-done summary").click()
                    playwright.expect(student.locator(".mx-asg-done .mx-ws-badge")).to_contain_text("נבדק · 90")
                    assert sorted(s["version"] for s in store.subs.values()) == [1, 2]
                    assert not (s_errors or t_errors), (s_errors, t_errors)
                finally:
                    browser.close()
        finally:
            server.should_exit = True
            thread.join(timeout=5)
