"""Updates reach every device (serve-fresh-files): the page and its files are revalidated, unchanged files are a 304."""
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
