"""Worksheets end to end: a real server (rows and files in memory) and a real browser for the teacher and the student.

The teacher attaches a PDF to an assignment, a student opens it and hands in photos of a solution, the teacher checks it
with a score and a comment, and the student sees the check. Then the teacher removes the worksheet, after confirming."""
import io
import socket
import threading
import time
import urllib.parse

import pytest
from PIL import Image

from app.main import create_app
from test_assignments import MemoryAssignments
from test_worksheets import MemoryWorksheets, pdf

playwright = pytest.importorskip("playwright.sync_api")
TEACHER, STUDENT = "aaaaaaaa-0000-4000-8000-000000000001", "aaaaaaaa-0000-4000-8000-000000000002"
mail = {TEACHER: "teacher@test.invalid", STUDENT: "dana@test.invalid"}


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


class FakeGrader:
    """The AI's check of a homework submission: a fixed suggestion."""

    def __init__(self):
        self.calls = []

    def grade(self, title, sheet_pages, solution_pages):
        self.calls.append((title, len(sheet_pages), len(solution_pages)))
        return {"readable": True, "score": 70, "comment": "כמעט! שימו לב לתרגיל 2", "usage": None}


class NoAnswers:
    configured = False

    def quiz(self, *args, **kwargs):
        from app.answer_scans import ScanError
        raise ScanError(503, "not_here")

    review = quiz


def photo_file(tmp_path, name, color):
    path = tmp_path / name
    Image.new("RGB", (600, 800), color).save(path, "JPEG")
    return str(path)


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
def school(monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")   # the AI check of homework follows the open-ended lock
    app = create_app(auth=SchoolAuth())
    app.state.homework_grader = FakeGrader()
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


def uvicorn():
    import uvicorn as u
    return u


def open_tasks(page, url):
    page.goto(url)
    page.locator('[data-act="class-report"]').click()
    sheet = page.locator(".mx-report-sheet")
    sheet.locator("[data-report-tab=tasks]").click()
    return sheet


def test_a_worksheet_from_upload_to_hand_in_to_check(school, tmp_path):
    url, app = school
    store = app.state.worksheets
    sheet_pdf = tmp_path / "pythagoras.pdf"
    sheet_pdf.write_bytes(pdf(2))
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            # ---- the teacher attaches a PDF to a new assignment
            teacher, t_errors = session(browser, TEACHER)
            sheet = open_tasks(teacher, url)
            sheet.locator("[data-asg-new]").click()
            form = sheet.locator("[data-asg-form]")
            form.locator("[name=title]").fill("שיעורי בית")
            form.locator("[name=due_on]").fill("2099-01-01")
            status = form.locator("[data-ws-status]")
            form.locator("[data-ws-upload]").click()
            playwright.expect(status).to_have_text("כתבו שם לשיעורי הבית.")
            form.locator("[name=ws_title]").fill("שיעורי בית – פיתגורס")
            form.locator("[name=ws_files]").set_input_files(str(sheet_pdf))
            form.locator("[data-ws-upload]").click()
            playwright.expect(form.locator("[data-ws-list] li")).to_have_count(1)
            playwright.expect(form.locator("[data-ws-list]")).to_contain_text("2 עמ׳ · PDF")
            playwright.expect(status).to_contain_text("הועלו")
            form.locator("button[type=submit]").click()
            card = sheet.locator(".mx-asg-t")
            playwright.expect(card).to_contain_text("שיעורי בית: שיעורי בית – פיתגורס")
            playwright.expect(card.locator(".mx-ws-sum")).to_contain_text("הגישו 0 מתוך 1 · 1 לא הגישו · 0 ממתינים לבדיקה")
            (assignment,) = app.state.assignments.rows.values()
            (wid,) = store.rows
            assert assignment["items"] == [{"kind": "worksheet", "id": wid}]

            # ---- the student opens it and hands in two photos
            student, s_errors = session(browser, STUDENT)
            student.goto(url)
            student.locator('.mx-nav [data-view="path"]').click()
            asg = student.locator(".mx-asgs .mx-asg")
            playwright.expect(asg).to_contain_text("שיעורי בית: שיעורי בית – פיתגורס")
            playwright.expect(asg).to_contain_text("0 מתוך 1 הושלמו")
            asg.locator("[data-asg-go]").click()                                        # the continue button opens it
            ws = student.locator(".mx-ws-sheet")
            playwright.expect(ws.locator("#mxTitle")).to_have_text("שיעורי בית – פיתגורס")
            playwright.expect(ws.locator(".mx-ws-pages img")).to_have_count(2)
            student.wait_for_function("[...document.querySelectorAll('.mx-ws-pages img')].every(i => i.complete && i.naturalWidth > 0)")
            with student.expect_download() as got:
                ws.locator("[data-ws-download]").click()
            assert got.value.suggested_filename == "שיעורי בית – פיתגורס.pdf"
            ws.locator("[data-ws-file]").set_input_files([photo_file(tmp_path, "a.jpg", "red"), photo_file(tmp_path, "b.jpg", "blue")])
            playwright.expect(ws.locator(".mx-ws-chosen li")).to_have_count(2)
            ws.locator('[data-ws-up="1"]').click()                                      # blue first now
            # a page written on the board joins the hand-in like a photo (then it is dropped again: two pages go in)
            ws.locator("[data-ws-board]").click()
            board = student.locator(".mx-board.full")
            playwright.expect(board).to_be_visible()
            box = board.locator("canvas").bounding_box()
            student.mouse.move(box["x"] + 60, box["y"] + 60)
            student.mouse.down(); student.mouse.move(box["x"] + 200, box["y"] + 160, steps=8); student.mouse.up()
            board.locator(".mx-board-send").click()
            playwright.expect(ws.locator(".mx-ws-chosen li")).to_have_count(3)
            playwright.expect(board).to_have_count(0)
            ws.locator('[data-ws-drop="2"]').click()
            playwright.expect(ws.locator(".mx-ws-chosen li")).to_have_count(2)
            ws.locator("[data-ws-send]").click()
            playwright.expect(ws.locator(".mx-ws-done")).to_contain_text("הוגש")
            playwright.expect(ws).to_contain_text("ההגשה נשלחה למורה")
            (sub,) = store.subs.values()
            assert len(sub["page_keys"]) == 2
            with Image.open(io.BytesIO(store.files[sub["page_keys"][0]][0])) as first:
                assert first.getpixel((10, 10))[2] > 150                                # the reordered page went first
            ws.locator(".mx-x").click()
            playwright.expect(student.locator(".mx-asgs .mx-asg")).to_have_count(0)     # done: the only item
            playwright.expect(student.locator(".mx-asg-done summary")).to_have_text("הושלמו (1)")

            # ---- the teacher checks it
            sheet = open_tasks(teacher, url)
            card = sheet.locator(".mx-asg-t")
            playwright.expect(card.locator(".mx-ws-sum")).to_contain_text("הגישו 1 מתוך 1 · 0 לא הגישו · 1 ממתינים לבדיקה")
            # the הגשות tab lists it by student and kind, and opens it for checking
            sheet.locator("[data-report-tab=subs]").click()
            dana = sheet.locator(".mx-report-student", has_text="dana")
            playwright.expect(dana).to_contain_text("1 ממתינות לבדיקה")
            playwright.expect(dana.locator("h5")).to_have_text(["שיעורי בית", "בחנים מסכמים", "מבחני תרגול · מהמכשיר"])
            playwright.expect(dana.locator("section").first).to_contain_text("שיעורי בית – פיתגורס")
            playwright.expect(dana).to_contain_text("הבחנים אינם זמינים כרגע")      # the test server has no quiz sittings
            playwright.expect(dana).to_contain_text("עוד לא נעשה מבחן תרגול")
            dana.locator("[data-ws-sub]").click()
            review = sheet.locator(".mx-ws-review")
            playwright.expect(review).to_contain_text("dana")
            playwright.expect(review.locator(".mx-ws-pages img")).to_have_count(2)
            teacher.wait_for_function("[...document.querySelectorAll('.mx-ws-review img')].every(i => i.complete && i.naturalWidth > 0)")
            check = review.locator("[data-ws-check]")
            review.locator("[data-ws-ai]").click()                                      # the AI suggests a score and a comment
            playwright.expect(check.locator("[name=score]")).to_have_value("70")
            playwright.expect(check.locator("[name=comment]")).to_have_value("כמעט! שימו לב לתרגיל 2")
            playwright.expect(review.locator("[data-ws-ai-status]")).to_contain_text("הצעת ה־AI הוכנסה לטופס")
            assert app.state.homework_grader.calls == [("שיעורי בית – פיתגורס", 2, 2)]   # the sheet's pages, the solution's
            assert not list(store.subs.values())[0]["checked_at"]                       # a suggestion is not saved
            check.locator("[name=score]").fill("120")
            check.locator("button[type=submit]").click()
            playwright.expect(check.locator("[role=status]")).to_contain_text("בין 0 ל־100")
            check.locator("[name=score]").fill("85")
            check.locator("[name=comment]").fill("יפה, שימי לב ליחידות")
            check.locator("button[type=submit]").click()
            playwright.expect(sheet).to_contain_text("הבדיקה נשמרה")
            playwright.expect(sheet.locator(".mx-report-student", has_text="dana")).to_contain_text("נבדק, ציון 85")
            sheet.locator("[data-report-tab=tasks]").click()
            playwright.expect(sheet.locator(".mx-ws-sum")).to_contain_text("0 ממתינים לבדיקה")
            playwright.expect(sheet.locator("[data-ws-sub]")).to_have_text("✔ 85")
            (sub,) = store.subs.values()
            assert (sub["score"], sub["comment"]) == (85, "יפה, שימי לב ליחידות") and sub["checked_at"]

            # ---- the student sees the check, and cannot hand in again
            student.reload()
            student.locator('.mx-nav [data-view="path"]').click()
            done = student.locator(".mx-asg-done")
            done.locator("summary").click()
            playwright.expect(done.locator(".mx-ws-badge")).to_have_text("נבדק · 85")
            playwright.expect(done.locator(".mx-ws-comment")).to_contain_text("יפה, שימי לב ליחידות")
            done.locator("[data-ws-open]").click()
            playwright.expect(ws.locator(".mx-ws-checked")).to_contain_text("ציון 85")
            assert ws.locator("[data-ws-pick]").count() == 0

            # ---- the teacher removes the worksheet: confirmed, with how many handed in
            asked = []
            teacher.once("dialog", lambda d: (asked.append(d.message), d.accept()))
            sheet = open_tasks(teacher, url)
            sheet.locator("[data-asg-edit]").click()
            form = sheet.locator("[data-asg-form]")
            assert form.locator("[name=skill], [name=quiz], [name=exam]").count() == 0     # a teacher gives worksheets only
            form.locator(f'[data-ws-remove="{wid}"]').click()
            assert asked and "1 תלמידים כבר הגישו" in asked[0]
            playwright.expect(form.locator("[data-ws-list] li")).to_have_count(0)
            form.locator("button[type=submit]").click()
            playwright.expect(form.locator(":scope > .mx-row > [role=status]")).to_have_text("העלו שיעורי בית אחד לפחות.")
            form.locator("[name=ws_title]").fill("שיעורי בית חדשים")                               # another worksheet in its place
            form.locator("[name=ws_files]").set_input_files(photo_file(tmp_path, "new.jpg", "green"))
            form.locator("[data-ws-upload]").click()
            playwright.expect(form.locator("[data-ws-list] li")).to_have_count(1)
            form.locator("button[type=submit]").click()
            playwright.expect(sheet.locator(".mx-asg-t")).not_to_contain_text("פיתגורס")
            playwright.expect(sheet.locator(".mx-asg-t")).to_contain_text("שיעורי בית חדשים")
            assert wid not in store.rows and not store.subs and len(store.rows) == 1
            assert not t_errors and not s_errors
        finally:
            browser.close()


def test_without_worksheets_the_form_has_no_upload(school):
    url, app = school
    app.state.worksheets.fail = True
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            teacher, errors = session(browser, TEACHER)
            sheet = open_tasks(teacher, url)
            sheet.locator("[data-asg-new]").click()
            playwright.expect(sheet.locator("[data-asg-form]")).to_be_visible()
            assert sheet.locator(".mx-ws-field").count() == 0
            assert not errors
        finally:
            browser.close()


def test_the_teacher_sees_their_classes_on_the_home_screen(school):
    url, _ = school
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            teacher, errors = session(browser, TEACHER)
            teacher.goto(url)
            card = teacher.locator(".mx-classes")
            playwright.expect(card.locator("h2")).to_have_text("הכיתות שלי")
            playwright.expect(card.locator(".mx-myclass")).to_have_count(1)
            playwright.expect(card.locator(".mx-myclass")).to_contain_text("ט׳1")
            playwright.expect(card.locator(".mx-myclass")).to_contain_text("1 תלמידים")     # dana; the teacher is not counted
            playwright.expect(card.locator(".mx-ai-left")).to_contain_text("3 בקשות AI")
            card.locator(".mx-myclass").click()
            playwright.expect(teacher.locator(".mx-report-sheet")).to_contain_text("dana")    # the class's students
            student, s_errors = session(browser, STUDENT)
            student.goto(url)
            playwright.expect(student.locator(".mx-subject-grid, .mx-star").first).to_be_visible()
            assert student.locator(".mx-classes").count() == 0
            assert not errors and not s_errors
        finally:
            browser.close()
