"""Focus practice end to end: the class teacher gives skills to one student from the report; only that student sees
it, marked as personal, and the report counts only them."""
import socket
import threading
import time

import pytest

from app.main import create_app
from test_assignments import MemoryAssignments
from test_worksheets import MemoryWorksheets
from test_worksheets_browser import NoAnswers, uvicorn

playwright = pytest.importorskip("playwright.sync_api")
TEACHER, DANA, YOSSI = ("bbbbbbbb-0000-4000-8000-00000000000%d" % i for i in (1, 2, 3))
mail = {TEACHER: "teacher@test.invalid", DANA: "dana@test.invalid", YOSSI: "yossi@test.invalid"}


class SchoolAuth:
    url, key, secret = "https://test.invalid", "public-test", "server-test"
    teachers = developers = frozenset()

    def user(self, token):
        return {"id": token, "email": mail[token]} if token in mail else None

    def classes(self, fresh=False):
        return [{"id": 3, "name": "ט׳1", "lessons": ["t", "k"], "teachers": [mail[TEACHER]],
                 "emails": list(mail.values()), "nicknames": {}, "exams": []}]

    def access_for(self, _id, **kwargs):
        return None

    def user_accounts(self, emails):
        return {email: {"id": uid, "name": ""} for uid, email in mail.items() if email in emails}

    def _admin(self, path, method="GET", body=None, prefer=""):
        from app.auth import AuthUnavailable
        if path.startswith("/rest/v1/math_progress"):
            return []
        raise AuthUnavailable("supabase answered 404: no other tables here")


def session(browser, uid):
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    ctx.add_init_script('''window.supabase={createClient:()=>({auth:{
      getSession:async()=>({data:{session:{access_token:"%s",user:{id:"%s"}}}}),
      onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),signOut:async()=>{}
    }})};''' % (uid, uid))
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page, errors


@pytest.fixture
def school():
    app = create_app(auth=SchoolAuth())
    app.state.assignments, app.state.worksheets, app.state.answers = MemoryAssignments(), MemoryWorksheets(), NoAnswers()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn().Server(uvicorn().Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", app
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def test_the_teacher_gives_focus_practice_to_one_student(school):
    url, app = school
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            teacher, t_errors = session(browser, TEACHER)
            teacher.goto(url)
            teacher.locator('[data-act="class-report"]').click()
            sheet = teacher.locator(".mx-report-sheet")
            sheet.locator("[data-report-tab=tasks]").click()
            sheet.locator("[data-asg-focus-new]").click()
            form = sheet.locator("[data-focus-form]")
            form.locator("button[type=submit]").click()
            playwright.expect(form.locator(".mx-row [role=status]")).to_have_text("בחרו לפחות תלמיד אחד.")
            form.locator('[name=student][value="dana@test.invalid"]').check()
            form.locator("details", has_text="טכניקה אלגברית 1").locator("summary").click()
            form.locator('[name=skill][value="t_ext"]').check()
            form.locator("[name=title]").fill("חיזוק פילוג")
            form.locator("[name=due_on]").fill("2099-01-01")
            form.locator("button[type=submit]").click()
            card = sheet.locator(".mx-asg-t")
            playwright.expect(card).to_contain_text("אישי")
            playwright.expect(card).to_contain_text("תרגול ממוקד ל: dana")
            playwright.expect(card.locator(".mx-asg-count")).to_contain_text("0 מתוך 1 תלמידים סיימו")   # only Dana counts
            (row,) = app.state.assignments.rows.values()
            assert row["student_emails"] == ["dana@test.invalid"] and row["items"] == [{"kind": "skill", "id": "t_ext"}]

            dana, d_errors = session(browser, DANA)
            dana.goto(url)
            dana.locator('.mx-nav [data-view="home"]').click()
            asg = dana.locator(".mx-asgs .mx-asg")
            playwright.expect(asg).to_contain_text("חיזוק פילוג")
            playwright.expect(asg.locator(".mx-asg-personal")).to_have_text("🎯 אישי")

            yossi, y_errors = session(browser, YOSSI)
            with yossi.expect_response(lambda r: "/api/math/assignments" in r.url) as got:
                yossi.goto(url)
            assert got.value.json()["assignments"] == []
            yossi.locator('.mx-nav [data-view="home"]').click()
            playwright.expect(yossi.locator(".mx-continue")).to_be_visible()
            playwright.expect(yossi.locator(".mx-asgs")).to_have_count(0)   # not given to Yossi
            assert not (t_errors or d_errors or y_errors), (t_errors, d_errors, y_errors)
        finally:
            browser.close()
