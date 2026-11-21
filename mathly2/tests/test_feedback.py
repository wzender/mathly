"""Suggestions and feedback (feedback.py): anyone signed in sends one; only the developer reads them and marks them handled."""
import pytest
from fastapi.testclient import TestClient

from mathly2 import feedback
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_boardwork_api import auth

KID, TEACHER, DEV = "kid@school.test", "t@school.test", "dev@school.test"


def world():
    store = InMemoryStore()
    klass = store.create_class("setup", "ט", lessons=["t"], teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    app = create_app(Settings(teachers=frozenset({TEACHER}), developers=frozenset({DEV})), store=store)
    return TestClient(app), store


def test_anyone_signed_in_sends_and_only_the_developer_reads_and_marks_it():
    client, store = world()
    sent = client.post("/api/feedback", headers=auth(KID), json={"kind": "bug", "body": "  הכפתור לא עובד  ", "page": "#/subject/math"})
    assert sent.status_code == 201
    client.post("/api/feedback", headers=auth(TEACHER), json={"kind": "idea", "body": "עוד שאלות על מקבילית"})
    assert client.get("/api/feedback", headers=auth(KID)).status_code == 403
    assert client.get("/api/feedback", headers=auth(TEACHER)).status_code == 403
    rows = client.get("/api/feedback", headers=auth(DEV)).json()
    assert [r["kind"] for r in rows] == ["idea", "bug"]                                     # the newest first
    bug = rows[1]
    assert bug["body"] == "הכפתור לא עובד" and bug["email"] == KID and bug["roles"] == ["student"] and bug["page"] == "#/subject/math"
    done = client.post(f"/api/feedback/{bug['id']}/handled", headers=auth(DEV), json={"handled": True}).json()
    assert done["handled_at"]
    assert client.post(f"/api/feedback/{bug['id']}/handled", headers=auth(DEV), json={"handled": False}).json()["handled_at"] is None
    assert client.post("/api/feedback/999/handled", headers=auth(DEV), json={"handled": True}).status_code == 404


def test_empty_too_long_or_too_many_are_refused():
    client, store = world()
    assert client.post("/api/feedback", headers=auth(KID), json={"body": "   "}).status_code == 422
    assert client.post("/api/feedback", headers=auth(KID), json={"body": "x" * 2001}).status_code == 422
    assert client.post("/api/feedback", headers=auth(KID), json={"kind": "spam", "body": "x"}).status_code == 422
    for _ in range(feedback.DAILY_LIMIT):
        assert client.post("/api/feedback", headers=auth(KID), json={"body": "עוד רעיון"}).status_code == 201
    assert client.post("/api/feedback", headers=auth(KID), json={"body": "ועוד אחד"}).status_code == 429


@pytest.fixture
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_in_the_browser_a_student_sends_and_the_developer_marks_it_handled(browser):
    client, store = world()
    with running(client.app) as url:
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        page.goto(url)
        page.fill("#email", KID)
        page.click("#dev button")
        page.wait_for_selector("#feedback")
        page.click("#feedback")
        page.wait_for_selector("#fb-form")
        page.check("input[name=kind][value=bug]")
        page.fill("#fb-body", "הכוכבים לא מתעדכנים")
        page.click("#fb-send")
        page.wait_for_selector("#fb-thanks")
        page.keyboard.press("Escape")
        page.wait_for_selector("#fb-form", state="detached")
        page.click("#out")
        page.wait_for_selector("form#dev")
        page.fill("#email", DEV)
        page.click("#dev button")
        page.wait_for_selector("#nav .roles")
        page.click("#nav [data-role='developer']")
        page.wait_for_selector("#fb-open li")
        assert "הכוכבים לא מתעדכנים" in page.inner_text("#fb-open") and KID in page.inner_text("#fb-open") and "1 פתוחות" in page.inner_text("#fb-open-count")
        page.click("#fb-open [data-handled]")
        page.wait_for_selector("#fb-none")
        assert "טופלו (1)" in page.inner_text("#feedback-card")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
