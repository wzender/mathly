"""Preparing for an exam: the exam names its units, and the student sees how ready they are and a plan of steps, with a
daily amount and each step checked off from their progress."""
import json
import socket
import threading
import time
from datetime import date, datetime, timedelta, timezone

import pytest

from app.main import create_app
from test_assignments import MemoryAssignments
from test_focus_browser import DANA, SchoolAuth, mail, session
from test_worksheets import MemoryWorksheets
from test_worksheets_browser import NoAnswers, uvicorn

playwright = pytest.importorskip("playwright.sync_api")


class ExamAuth(SchoolAuth):
    exams = []

    def classes(self, fresh=False):
        return [{**super().classes()[0], "exams": self.exams}]


@pytest.fixture
def exam_server():
    auth = ExamAuth()
    app = create_app(auth=auth)
    app.state.assignments, app.state.worksheets, app.state.answers = MemoryAssignments(), MemoryWorksheets(), NoAnswers()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn().Server(uvicorn().Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", auth
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# unit t: t_ext finished lately, t_simplify finished long ago (fading), t_ext_eq tried, t_area and t_formulas not started
PROGRESS = {"done": {"t_ext": ago(1), "t_simplify": ago(40)}, "seen": {"t_ext": ago(1), "t_simplify": ago(40), "t_ext_eq": ago(2)},
            "tries": {"t_ext_eq": 2}, "updated": 1}


def with_progress(page, progress):
    k = json.dumps("mathly.progress.v1:" + mail[DANA])   # only the first time: a reload keeps what the page saved
    page.add_init_script("if(!localStorage.getItem(%s)) localStorage.setItem(%s, %s)" % (k, k, json.dumps(json.dumps(progress))))


def test_the_student_sees_readiness_and_a_plan_with_a_daily_amount(exam_server):
    url, auth = exam_server
    auth.exams = [{"subject": "מתמטיקה", "date": (date.today() + timedelta(days=3)).isoformat(), "units": ["t"], "note": "פרק 3"}]
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, DANA)
            with_progress(page, PROGRESS)
            page.goto(url)
            page.locator('[data-subject="מתמטיקה"]').click()
            page.locator(".mx-prep-open").click()
            prep = page.locator(".mx-prep-sheet")
            playwright.expect(prep.locator("#mxTitle")).to_have_text("הכנה למבחן במתמטיקה")
            playwright.expect(prep).to_contain_text("חומר למבחן: טכניקה אלגברית 1")
            playwright.expect(prep).to_contain_text("פרק 3")
            playwright.expect(prep.locator(".mx-prep-sum")).to_have_text("2 מתוך 5 מיומנויות הושלמו · 1 דועכות")
            playwright.expect(prep.locator(".mx-prep-skills li")).to_have_count(5)
            playwright.expect(prep.locator('.mx-prep-skills li[data-state="fading"]')).to_have_count(1)
            steps = prep.locator(".mx-prep-step")
            playwright.expect(steps).to_have_count(8)   # 3 not finished, 1 fading, the unit's quiz, the three quizzes
            playwright.expect(prep.locator(".mx-prep-plan")).to_contain_text("3 צעדים ביום")
            playwright.expect(prep.locator(".mx-prep-step.today")).to_have_count(3)
            playwright.expect(steps.nth(0)).to_contain_text("ללמוד ולסיים")
            playwright.expect(steps.nth(5)).to_contain_text("מבחן תרגול 1")
            playwright.expect(steps.nth(6)).to_contain_text("מבחן תרגול 2")
            playwright.expect(steps.nth(7)).to_contain_text("מבחן תרגול כמו במבחן")
            # a step done from progress made after the plan was opened
            page.evaluate("""() => { const k = Object.keys(localStorage).find(k => k.startsWith('mathly.progress.v1:'));
                const P = JSON.parse(localStorage.getItem(k)); P.done.t_area = new Date().toISOString(); localStorage.setItem(k, JSON.stringify(P)); }""")
            page.reload()
            page.locator('[data-subject="מתמטיקה"]').click()
            page.locator(".mx-prep-open").click()
            playwright.expect(prep.locator(".mx-prep-step.done")).to_have_count(1)
            playwright.expect(prep.locator(".mx-prep-step.done")).to_contain_text("השוואת שטחים")
            # the first quiz's step starts it, over the exam's units only; handed in, the step is done
            prep.locator('[data-hq="s1"]').click()
            sheet = page.locator(".mx-quiz-sheet")
            playwright.expect(sheet.locator(".mx-uchip")).to_have_text("מבחן תרגול 1")
            n = sheet.locator(".mx-quiz-dots button").count()
            for i in range(n):
                sheet.locator(".mx-choices button[data-right]").first.click()
                sheet.locator("[data-act=quiz-submit]" if i == n - 1 else "[data-act=quiz-next]").click()
            playwright.expect(sheet.locator("#mxTitle")).to_have_text(f"{n} מתוך {n} נכונות")
            qs = page.evaluate("""() => { const k = Object.keys(localStorage).find(k => k.startsWith('mathly.progress.v1:'));
                return JSON.parse(localStorage.getItem(k)).quizzes.at(-1).qs; }""")
            assert qs and all(q.startswith("t_") for q in qs)
            sheet.locator(".mx-x").click()
            page.locator(".mx-prep-open").click()
            playwright.expect(prep.locator(".mx-prep-step.done", has_text="מבחן תרגול 1")).to_have_count(1)
            assert not errors, errors
        finally:
            browser.close()


def test_the_day_before_the_exam_the_plan_has_no_daily_amount(exam_server):
    url, auth = exam_server
    auth.exams = [{"subject": "מתמטיקה", "date": (date.today() + timedelta(days=1)).isoformat(), "units": ["t"]},
                  {"subject": "מתמטיקה", "date": (date.today() + timedelta(days=9)).isoformat()}]   # no units: no preparation
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, DANA)
            with_progress(page, PROGRESS)
            page.goto(url)
            page.locator('[data-subject="מתמטיקה"]').click()
            playwright.expect(page.locator(".mx-prep-open")).to_have_count(1)
            page.locator(".mx-prep-open").click()
            prep = page.locator(".mx-prep-sheet")
            playwright.expect(prep.locator(".mx-uchip")).to_have_text("מחר")
            playwright.expect(prep.locator(".mx-prep-step")).to_have_count(8)   # the three quizzes at the end
            playwright.expect(prep.locator(".mx-prep-plan")).not_to_contain_text("צעדים ביום")
            playwright.expect(prep.locator(".mx-prep-step.today")).to_have_count(0)
            assert not errors, errors
        finally:
            browser.close()


def test_the_teacher_names_the_units_and_sees_how_ready_the_class_is(exam_server):
    from test_focus_browser import TEACHER
    url, auth = exam_server
    auth.exams = [{"subject": "מתמטיקה", "date": (date.today() + timedelta(days=5)).isoformat()}]
    saved = []

    def save(class_id, exams):
        saved.append(exams)
        auth.exams = exams
    auth.save_class_exams = save
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, TEACHER)
            page.goto(url)
            page.locator('[data-act="class-report"]').click()
            sheet = page.locator(".mx-report-sheet")
            sheet.locator("[data-report-tab=exams]").click()
            form = sheet.locator("[data-exam-form]")
            playwright.expect(sheet.locator(".mx-exam-t")).to_contain_text("בחרו את היחידות של המבחן")
            form.locator('[name=unit][value="t"]').check()
            form.locator("[name=note]").fill("פרק 3")
            form.locator("button[type=submit]").click()
            playwright.expect(sheet.locator(".mx-report")).to_contain_text("החומר למבחן נשמר")
            assert saved[-1][0]["units"] == ["t"] and saved[-1][0]["note"] == "פרק 3"
            playwright.expect(sheet.locator(".mx-exam-t .mx-report-table tbody tr")).to_have_count(5)   # the 5 skills of t
            playwright.expect(sheet.locator(".mx-exam-t")).to_contain_text("הכי רחוקים מהחומר")
            assert not errors, errors
        finally:
            browser.close()


def test_a_plan_saved_with_the_old_practice_exam_step_gets_the_three_quizzes(exam_server):
    url, auth = exam_server
    when = (date.today() + timedelta(days=5)).isoformat()
    auth.exams = [{"subject": "מתמטיקה", "date": when, "units": ["t"], "note": ""}]
    old = {**PROGRESS, "prep": {f"3|מתמטיקה|{when}": {"opened": ago(1), "steps": [{"k": "skill", "id": "t_area"}, {"k": "exam"}]}}}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, DANA)
            with_progress(page, old)
            page.goto(url)
            page.locator('[data-subject="מתמטיקה"]').click()
            page.locator(".mx-prep-open").click()
            steps = page.locator(".mx-prep-sheet .mx-prep-step")
            playwright.expect(steps).to_have_count(4)
            playwright.expect(steps.nth(1)).to_contain_text("מבחן תרגול 1")
            playwright.expect(steps.nth(3)).to_contain_text("מבחן תרגול כמו במבחן")
            assert not errors, errors
        finally:
            browser.close()


def test_home_highlights_the_lessons_to_finish_before_the_next_exam(exam_server):
    url, auth = exam_server
    auth.exams = [{"subject": "מתמטיקה", "date": (date.today() + timedelta(days=4)).isoformat(), "units": ["t", "k"]}]
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, DANA)
            with_progress(page, {**PROGRESS, "done": {**PROGRESS["done"], **{s: ago(1) for s in ("k_def", "k_angles", "k_diag", "k_axes")}}})
            page.goto(url)
            page.locator('[data-subject="מתמטיקה"]').click()
            page.locator('.mx-nav [data-view="home"]').click()
            lessons = page.locator(".mx-home-lessons")
            playwright.expect(lessons.locator("h3")).to_have_text("להשלים לפני המבחן: שיעור אחד")
            playwright.expect(lessons.locator("li.todo")).to_have_count(1)                # unit t: 2 of 5 skills
            playwright.expect(lessons.locator("li.todo")).to_contain_text("2 מתוך 5 מיומנויות")
            playwright.expect(lessons.locator("li.done")).to_contain_text("✓ הושלם")       # unit k: all done
            lessons.locator("li.todo button").click()                                    # opens the lesson on the path
            playwright.expect(page.locator('.mx-nav [data-view="path"]')).to_have_attribute("aria-current", "page")
            assert not errors, errors
        finally:
            browser.close()


def test_the_teacher_adds_and_deletes_an_exam_on_the_classs_table(exam_server):
    from test_focus_browser import TEACHER
    url, auth = exam_server
    auth.exams = []

    def save(class_id, exams):
        auth.exams = exams
    auth.save_class_exams = save
    day = (date.today() + timedelta(days=12)).isoformat()
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, TEACHER)
            page.on("dialog", lambda d: d.accept())
            page.goto(url)
            page.locator('[data-act="class-report"]').click()
            sheet = page.locator(".mx-report-sheet")
            sheet.locator("[data-report-tab=exams]").click()
            playwright.expect(sheet.locator(".mx-report")).to_contain_text("אין מבחנים קרובים")
            form = sheet.locator("[data-exam-add]")
            form.locator("[name=date]").fill(day)
            form.locator('[name=unit][value="t"]').check()
            form.locator("[name=note]").fill("פרק 3")
            form.locator("button[type=submit]").click()
            playwright.expect(sheet.locator(".mx-flash")).to_contain_text("נוסף ללוח")
            playwright.expect(sheet.locator(".mx-exam-t h4")).to_contain_text("מתמטיקה")
            assert auth.exams == [{"subject": "מתמטיקה", "date": day, "units": ["t"], "note": "פרק 3"}]
            sheet.locator("[data-exam-del]").click()
            playwright.expect(sheet.locator(".mx-flash")).to_contain_text("נמחק")
            assert auth.exams == []
            assert not errors, errors
        finally:
            browser.close()
