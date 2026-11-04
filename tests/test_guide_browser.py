"""Browser checks of the user guide (static/guide.js): the "?" button opens it, with a tab for students and one for teachers.
Optional, like the other browser tests: pip install playwright && playwright install chromium."""
import socket
import threading
import time

import pytest
import uvicorn

from app.main import create_app

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def server():
    app = create_app()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        srv = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=srv.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not srv.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            srv.should_exit = True
            thread.join(timeout=5)


def test_guide_opens_with_student_and_teacher_tabs(server):
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            ctx = browser.new_context(viewport={"width": 390, "height": 844})
            ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            ctx.route("https://fonts.googleapis.com/**", lambda route: route.abort())
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(server)
            assert page.locator("#boot [data-guide-open]").count() == 1   # on the sign-in screen
            page.locator("#mathView [data-guide-open]").first.click()   # and in the app's header
            guide = page.get_by_role("dialog", name="איך משתמשים באפליקציה")
            playwright.expect(guide).to_be_visible()
            playwright.expect(page.locator("#mgS")).to_contain_text("בוחן מסכם")
            playwright.expect(page.locator("#mgT")).to_be_hidden()
            page.get_by_role("tab", name="למורים").click()
            playwright.expect(page.locator("#mgT")).to_contain_text("הכיתה שלי")
            playwright.expect(page.locator("#mgS")).to_be_hidden()
            page.keyboard.press("Escape")
            playwright.expect(guide).to_be_hidden()
            assert errors == []
        finally:
            browser.close()
