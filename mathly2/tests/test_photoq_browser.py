"""Photographed questions in a real browser: home's button, the code for the phone, the question on the board, the grade, and the teacher's
approval (photoq.py with a fake AI)."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.bank import load_bank                                         # noqa: E402
from mathly2.config import Settings                                         # noqa: E402
from mathly2.main import create_app                                         # noqa: E402
from mathly2.store import InMemoryStore                                     # noqa: E402
from mathly2.tests.serve import board_written, offline_formulas, running   # noqa: E402
from mathly2.tests.test_boardwork_api import auth, png                     # noqa: E402
from mathly2.tests.test_photoq_api import KID, TEACHER, FakeAI             # noqa: E402

PHONE = {"width": 390, "height": 844}


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def sign_in(browser, url, who):
    page = offline_formulas(browser.new_page(viewport=PHONE))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script("window.__photoPollComputer = 200;")
    page.goto(url)
    page.fill("#email", who)
    page.click("#dev button")
    page.errors = errors
    return page


def test_a_student_photographs_solves_and_gets_a_grade_and_the_teacher_approves(browser):
    bank, store = load_bank(), InMemoryStore()
    klass = store.create_class("setup", "ט", lessons=[l["id"] for l in bank.lessons][:3], teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    app = create_app(Settings(teachers=frozenset({TEACHER})), bank=bank, store=store, reviewer=FakeAI(score=85))
    app.state.run_photoq = lambda target, app_, *args: target(app_, *args)
    from fastapi.testclient import TestClient
    api = TestClient(app)
    with running(app) as url:
        page = sign_in(browser, url, KID)
        board_written(page, pictures=True)
        page.click(".subject-card")
        page.click("#home-photoq")
        page.wait_for_selector("#pq-new")
        assert "נשארו 5 צילומים היום" in page.inner_text("#pq-left")
        page.click("#pq-new")
        page.wait_for_selector("#request-code")
        code = page.inner_text("#request-code")
        phone = api.get("/api/photo-requests/open?device=phone", headers=auth(KID)).json()[0]                  # the phone sees the same code
        assert phone["code"] == code
        api.post(f"/api/photo-requests/{phone['id']}/picture", content=png(), headers={**auth(KID), "Content-Type": "image/png"})
        page.wait_for_selector("#pq-q")
        assert "2x + 3 = 11" in page.inner_text("#pq-q") and page.locator("#pq-final").count() == 1
        assert "(הצעה)" in page.inner_text("#pq-skill") and page.locator(".pq-layer [data-board-toggle]").count() == 1
        page.fill("#pq-final", "4")
        page.click("#pq-submit")
        page.wait_for_selector("#pq-result")
        assert page.inner_text("#pq-result .qz-grade b") == "85" and "דרך טובה" in page.inner_text("#pq-result")
        assert "השאלה נשלחה למורה" in page.inner_text("#pq-result")
        assert page.errors == []
        teacher = sign_in(browser, url, TEACHER)
        teacher.wait_for_selector("#teaching")
        teacher.click("#teacher-tabs [data-tab=ai]")
        teacher.wait_for_selector("#pq-teacher-list [data-pq]")
        assert KID in teacher.inner_text("#pq-teacher-list") and "$x = 4$" in teacher.input_value("[data-field=answer]")
        teacher.click("[data-decide=approve]")
        teacher.wait_for_selector("#pq-none")
        teacher.click("#pq-filter [data-filter=approved]")
        teacher.wait_for_selector("#pq-teacher-list [data-pq]")
        assert teacher.errors == []


def test_help_gives_a_direction_and_a_step_answers_a_question_and_caps_the_grade(browser):
    bank, store = load_bank(), InMemoryStore()
    klass = store.create_class("setup", "ט", lessons=[l["id"] for l in bank.lessons][:3], teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    app = create_app(Settings(teachers=frozenset({TEACHER})), bank=bank, store=store, reviewer=FakeAI(score=95))
    app.state.run_photoq = lambda target, app_, *args: target(app_, *args)
    from fastapi.testclient import TestClient
    api = TestClient(app)
    api.get("/api/me", headers=auth(KID))
    req = api.post("/api/photo-requests", headers=auth(KID), json={"purpose": "question", "device": "pc"}).json()
    pic = api.post(f"/api/photo-requests/{req['id']}/picture", content=png(), headers={**auth(KID), "Content-Type": "image/png"}).json()
    qid = api.post("/api/photo-questions", headers=auth(KID), json={"picture_id": pic["picture_id"]}).json()["id"]
    with running(app) as url:
        page = sign_in(browser, url, KID)
        board_written(page, pictures=True)
        page.wait_for_selector(".subject-card")
        page.evaluate(f"location.hash = '#/photoq/{qid}'")
        page.wait_for_selector("#pq-help-open")
        page.click("#pq-help-open")
        page.wait_for_selector("#pq-rungs")
        assert "(מקסימום 90)" in page.inner_text("#pq-rungs") and page.inner_text("#pq-cap b") == "100"
        page.click("[data-help=direction]")
        page.wait_for_function("document.querySelector('#pq-cap b').textContent === '90'")
        page.click("[data-help=step]")
        page.wait_for_function("document.querySelector('#pq-cap b').textContent === '75'")
        assert "צעד 1" in page.inner_text("#pq-chat")
        page.fill("#pq-ask-text", "למה מחסירים 3?")
        page.click("#pq-ask button[type=submit]")
        page.wait_for_function("document.querySelectorAll('#pq-chat .pq-msg').length === 6")
        assert "נסו לבודד" in page.inner_text("#pq-chat") and "המורה יכול/ה לראות את השיחה" in page.inner_text("#pq-help")
        page.click("#pq-submit")
        page.wait_for_selector("#pq-result")
        assert page.inner_text("#pq-result .qz-grade b") == "75"                              # 95 from the check, capped by the help taken
        page.wait_for_selector("#pq-help-open, #pq-chat")
        assert page.errors == []
