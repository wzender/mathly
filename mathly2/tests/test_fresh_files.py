"""Updates reach every device (serve-fresh-files): the page and its files are revalidated, unchanged files are a 304."""
import pytest
from fastapi.testclient import TestClient

from mathly2.config import Settings
from mathly2.main import create_app


def client():
    return TestClient(create_app(Settings()))


def test_the_page_and_static_files_must_be_checked_before_reuse():
    c = client()
    assert c.get("/").headers["cache-control"] == "no-cache"
    for path in ("/static/app.css", "/static/app.js", "/static/logo.svg"):
        response = c.get(path)
        assert response.status_code == 200 and response.headers["cache-control"] == "no-cache" and response.headers["etag"]


def test_an_unchanged_file_is_not_sent_again():
    c = client()
    etag = c.get("/static/app.css").headers["etag"]
    again = c.get("/static/app.css", headers={"If-None-Match": etag})
    assert again.status_code == 304 and again.content == b""


def test_api_routes_are_unchanged():
    assert "no-cache" not in client().get("/api/health").headers.get("cache-control", "")


def test_the_icon_is_served_unchanged_from_mathly1():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    response = client().get("/static/icons/icon-192.png")
    assert response.status_code == 200 and response.headers["content-type"] == "image/png"
    assert response.content == (root / "static" / "icons" / "icon-192.png").read_bytes()


def test_the_page_loads_with_its_icon_and_no_failed_request_or_console_error():
    import pytest
    playwright = pytest.importorskip("playwright.sync_api")
    from mathly2.tests.serve import offline_formulas, running
    with running(create_app(Settings())) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page())
        failed, errors = [], []
        page.on("response", lambda r: failed.append(r.url) if r.status >= 400 else None)
        page.on("requestfailed", lambda r: errors.append(r.url) if "mathjax" not in r.url else None)     # the test blocks MathJax on purpose
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "ERR_FAILED" not in m.text else None)
        page.goto(url)
        page.wait_for_selector("#signin")
        page.wait_for_timeout(500)
        assert page.get_attribute("link[rel=icon]", "href") == "/static/icons/icon-192.png"
        assert page.evaluate("fetch('/static/icons/icon-192.png').then(r => r.status)") == 200
        assert failed == [] and errors == []
        browser.close()


def test_the_page_asks_for_this_builds_files_and_every_answer_carries_the_build(tmp_path):
    from mathly2.main import build_of
    c = client()
    build = c.app.state.build
    page = c.get("/").text
    assert f"/static/app.css?v={build}" in page and f"/static/app.js?v={build}" in page and f'"build": "{build}"' in page
    assert "__BUILD__" not in page
    assert c.get("/api/health").headers["x-mathly-build"] == build
    assert c.get("/static/app.css").headers["x-mathly-build"] == build
    (tmp_path / "a.css").write_text("a{}")
    one = build_of(tmp_path)
    (tmp_path / "a.css").write_text("a{color:red}")
    assert build_of(tmp_path) != one                                          # a changed file is a new build


def test_an_app_left_open_after_an_update_reloads_at_the_next_screen():
    playwright = pytest.importorskip("playwright.sync_api")
    from mathly2.tests.serve import running
    with running(create_app(Settings())) as url, playwright.sync_playwright() as p:
        page = p.chromium.launch().new_page()
        page.goto(url)
        page.wait_for_selector("#email")
        page.evaluate("window.__kept = 1")
        page.route("**/api/**", lambda route: route.fulfill(response=route.fetch(), headers={**route.fetch().headers, "x-mathly-build": "newer"}))
        page.fill("#email", "kid@school.test")
        page.click("#dev button")                                               # an answer from a newer build: nothing happens yet
        page.wait_for_timeout(500)
        assert page.evaluate("window.__kept") == 1
        page.evaluate("location.hash = '#/somewhere'")                          # the next screen: the page reloads with the new files
        page.wait_for_function("window.__kept === undefined")


def _signed_in_page(p, url, delays):
    page = p.chromium.launch().new_page()
    page.add_init_script(f"window.__retryDelays = {delays};")
    page.goto(url)
    page.wait_for_selector("#email")
    return page


def test_while_the_site_updates_requests_are_sent_again_with_a_note_and_then_go_through():
    playwright = pytest.importorskip("playwright.sync_api")
    from mathly2.tests.serve import running
    with running(create_app(Settings())) as url, playwright.sync_playwright() as p:
        page = _signed_in_page(p, url, "[700, 700, 700]")
        calls = []

        def host_restarting(route):                                   # the host's own 503 page twice, then the server answers
            calls.append(1)
            if len(calls) <= 2:
                route.fulfill(status=503, body="<html>Starting</html>", content_type="text/html")
            else:
                route.continue_()
        page.route("**/api/me", host_restarting)
        page.fill("#email", "kid@school.test")
        page.click("#dev button")
        page.wait_for_selector("#updating-note")
        assert "מתעדכן" in page.inner_text("#updating-note")
        page.wait_for_selector("#updating-note", state="detached")
        page.wait_for_selector(".nav-email")                            # signed in after all
        assert len(calls) == 3


def test_an_update_that_does_not_end_says_so_and_our_own_503_is_not_sent_again():
    playwright = pytest.importorskip("playwright.sync_api")
    from mathly2.tests.serve import running
    with running(create_app(Settings())) as url, playwright.sync_playwright() as p:
        page = _signed_in_page(p, url, "[50, 50]")
        calls = []
        page.route("**/api/me", lambda route: (calls.append(1), route.fulfill(status=503, body="down", content_type="text/plain")))
        page.fill("#email", "kid@school.test")
        page.click("#dev button")
        page.wait_for_function("document.body.innerText.includes('האתר מתעדכן כרגע')")
        assert len(calls) == 3 and page.locator("#updating-note").count() == 0
        page = _signed_in_page(p, url, "[50, 50]")                       # a new browser: no session kept
        ours = []
        page.route("**/api/me", lambda route: (ours.append(1), route.fulfill(status=503, json={"detail": "מסד הנתונים לא ענה"})))
        page.fill("#email", "kid@school.test")
        page.click("#dev button")
        page.wait_for_function("document.body.innerText.includes('מסד הנתונים לא ענה')")
        assert len(ours) == 1                                           # the server answered: not sent again
