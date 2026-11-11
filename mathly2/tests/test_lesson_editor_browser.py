"""The worksheet upload and the lesson editor in a real browser (add-subjects-and-worksheets 6.2, 6.3)."""
import io

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from PIL import Image                                         # noqa: E402

from mathly2.ai import FakeAI                                 # noqa: E402
from mathly2.config import Settings                           # noqa: E402
from mathly2.main import create_app                           # noqa: E402
from mathly2.store import InMemoryStore                       # noqa: E402
from mathly2.tests.serve import running                       # noqa: E402

MGR = "mgr@school.test"
PHONE, DESKTOP = {"width": 390, "height": 844}, {"width": 1280, "height": 800}


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def pdf_file(tmp_path, pages=2):
    images = [Image.new("RGB", (600, 800), (255, 255, 255)) for _ in range(pages)]
    path = tmp_path / "sheet.pdf"
    images[0].save(path, "PDF", save_all=True, append_images=images[1:])
    return str(path)


def app_with(ai):
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    return create_app(Settings(), store=store, ai_client=ai), store


def open_subjects(browser, url, viewport):
    page = browser.new_page(viewport=viewport)
    page.route("**/mathjax@*/**", lambda route: route.abort())
    page.goto(url)
    page.fill("#email", MGR)
    page.click("#dev button")
    page.wait_for_selector("#mgr")
    page.click("#mgr-tabs [data-tab='subjects']")
    page.wait_for_selector("#worksheet-form")
    return page


def upload_new_subject(page, file):
    page.select_option("#ws-subject", "new")
    page.fill("#ws-new-name", "מדעים")
    page.set_input_files("#ws-files", file)
    page.click("#ws-go")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_upload_review_and_fix_a_drafted_lesson_and_every_change_is_kept(browser, tmp_path, viewport):
    app, store = app_with(FakeAI())
    with running(app) as url:
        page = open_subjects(browser, url, viewport)
        upload_new_subject(page, pdf_file(tmp_path))
        page.wait_for_selector("#lesson-editor .le-skill", timeout=15000)                    # the draft arrives (the editor polls)
        assert page.locator(".le-sheet img").count() == 2                                     # the worksheet beside the draft
        assert page.input_value("#le-name") == "תאים"
        first = page.locator(".le-question").first
        assert first.locator(".le-source").inner_text() == "מהדף"
        assert page.locator(".le-question .le-source", has_text="נכתב על ידי AI").count() > 0

        first.locator(".le-choice").nth(1).locator("[data-act=right]").check()                 # the second choice is the right one
        page.wait_for_function("document.getElementById('le-saved').textContent === 'נשמר'")
        page.click("#le-back")
        page.wait_for_selector("#subjects [data-open-lesson]")
        page.click("#subjects [data-open-lesson]")
        page.wait_for_selector("#lesson-editor .le-skill")
        first = page.locator(".le-question").first
        assert first.locator(".le-choice").nth(1).locator("[data-act=right]").is_checked()
        assert first.locator(".le-choice").nth(0).locator("select").count() == 1               # the old right one now needs a mistake
        assert first.locator(".le-source").inner_text() == "נכתב על ידי אדם"

        page.locator(".le-skill [data-act=add-q]").first.click()
        page.wait_for_function("document.getElementById('le-saved').textContent === 'נשמר'")
        added = page.locator(".le-question").last
        assert added.locator(".le-source").inner_text() == "נכתב על ידי אדם"
        added.locator("textarea").fill("שאלה חדשה $x$")
        page.wait_for_function("document.getElementById('le-saved').textContent === 'נשמר'")
        lesson = store.lessons_of()[0]
        assert lesson["draft"]["skills"][0]["questions"][-1]["question"] == "שאלה חדשה $x$" and lesson["published"] is None
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")


def test_a_failed_draft_says_why_and_trying_again_brings_the_draft(browser, tmp_path):
    fake = FakeAI()
    fake.fail_draft = ["overloaded"]
    app, store = app_with(fake)
    with running(app) as url:
        page = open_subjects(browser, url, DESKTOP)
        upload_new_subject(page, pdf_file(tmp_path, 1))
        page.wait_for_selector("#le-retry", timeout=15000)
        assert "עמוס" in page.inner_text("#le-status")
        page.click("#le-retry")
        page.wait_for_selector("#lesson-editor .le-skill", timeout=15000)
        assert page.locator("#le-retry").count() == 0
