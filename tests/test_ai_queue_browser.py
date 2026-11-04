"""In the browser: a student's quiz answers wait in the teacher's AI queue; the teacher sends them; the grade shows."""
import socket
import threading
import time

import pytest
import uvicorn

from app.answer_grading import validate_assessment
from app.main import create_app
from scan_support import OWNER, OTHER, answer_store, postgres_server
from test_ai_queue import ClassAuth, MemoryQueue
from test_answer_grading import assessment
from test_unit_quiz import photograph

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(autouse=True)
def grading_on(monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


@pytest.fixture
def queue_server(answer_store):
    app = create_app(auth=ClassAuth()); app.state.answers = answer_store
    app.state.ai_queue = MemoryQueue()
    calls = []

    class Grader:
        def grade(self, image, snapshot):
            if "fail" in calls:
                from app.math_photo import PhotoUnavailable
                raise PhotoUnavailable("x", "api_key_invalid", "AuthenticationError 401: invalid x-api-key")
            calls.append(snapshot["name"])
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
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", calls
        finally:
            server.should_exit = True; thread.join(timeout=5)


def page_of(browser, url, owner, errors):
    from test_answer_browser import session
    page = session(browser, owner=owner).new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.locator('.mx-nav [data-view="path"]').click()
    return page


def test_the_teacher_sends_a_students_quiz_answer_to_the_ai(queue_server, tmp_path):
    url, calls = queue_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        errors = []
        try:
            student = page_of(browser, url, OWNER, errors)
            playwright.expect(student.locator('[data-act="ai-queue"]')).to_have_count(0)   # a student has no queue
            student.locator('.mx-uquiz[data-uquiz="t"]').click()
            student.locator("[data-act=uq-start]").click()
            photograph(student, 0, tmp_path)
            paper = student.locator(".mx-uq-paper")
            paper.locator("[data-act=uq-submit]").click()
            paper.locator("[data-act=uq-submit]").click()   # past the warning about unanswered questions
            sheet = student.locator(".mx-uq-sheet")
            playwright.expect(sheet.locator(".mx-uq-verdict").first).to_have_text("מחכה למורה שיאשר את הבדיקה", timeout=15000)
            assert not calls

            teacher = page_of(browser, url, OTHER, errors)
            button = teacher.locator('.mx-acts [data-act="ai-queue"]').first
            playwright.expect(button).to_contain_text("1")
            button.click()
            card = teacher.locator(".mx-aq-card.pending")
            playwright.expect(card).to_have_count(1)
            playwright.expect(card.locator(".mx-aq-img")).to_be_visible()
            card.locator("[data-aq-send]").click()
            playwright.expect(teacher.locator(".mx-aq-card.done")).to_contain_text("נכונה · 100/100")
            assert len(calls) == 1

            sheet.locator('[data-act="close"]').last.click()
            student.locator('.mx-uquiz[data-uquiz="t"]').click()
            student.locator("[data-uq-result]").first.click()
            playwright.expect(student.locator(".mx-uq-verdict").first).to_have_text("נכון ומלא", timeout=10000)
            assert len(calls) == 1 and not errors, errors
        finally:
            browser.close()


def test_a_failed_send_has_an_error_details_button(queue_server, tmp_path):
    from app.math_photo import PhotoUnavailable
    url, calls = queue_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        errors = []
        try:
            student = page_of(browser, url, OWNER, errors)
            student.locator('.mx-uquiz[data-uquiz="t"]').click()
            student.locator("[data-act=uq-start]").click()
            photograph(student, 0, tmp_path)
            paper = student.locator(".mx-uq-paper")
            paper.locator("[data-act=uq-submit]").click()
            paper.locator("[data-act=uq-submit]").click()
            playwright.expect(student.locator(".mx-uq-verdict").first).to_have_text("מחכה למורה שיאשר את הבדיקה", timeout=15000)
            calls.append("fail")   # the grader below fails while this is in the list

            teacher = page_of(browser, url, OTHER, errors)
            teacher.locator('.mx-acts [data-act="ai-queue"]').first.click()
            teacher.locator(".mx-aq-card.pending [data-aq-send]").click()
            card = teacher.locator(".mx-aq-card.failed")
            playwright.expect(card.locator(".mx-aq-error")).to_have_text("הבדיקה נכשלה. אפשר לנסות שוב.")
            details = card.locator(".mx-error-details")
            playwright.expect(details.locator("code")).to_be_hidden()
            details.locator("summary").click()
            playwright.expect(details).to_contain_text("מפתח ה-API לא תקין")
            playwright.expect(details.locator("code")).to_have_text("AuthenticationError 401: invalid x-api-key")
            assert not errors, errors
        finally:
            browser.close()
