"""The developer's prompter in a real browser (add-prompter): write and save a text, get an AI outline, show it full screen,
keep what was typed across a reload, and delete it."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.ai import FakeAI                                 # noqa: E402
from mathly2.config import Settings                           # noqa: E402
from mathly2.main import create_app                           # noqa: E402
from mathly2.store import InMemoryStore                       # noqa: E402
from mathly2.tests.serve import running                       # noqa: E402

DEV = "dev@school.test"
PHONE, DESKTOP = {"width": 390, "height": 844}, {"width": 1280, "height": 800}


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_prompter(page, url):
    page.route("**/mathjax@*/**", lambda route: route.abort())
    page.goto(url)
    page.fill("#email", DEV)
    page.click("#dev button")
    page.wait_for_selector("#nav .roles")
    page.click("#nav [data-role='developer']")
    page.wait_for_selector("#pr-form")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390px", "1280px"])
def test_a_developer_writes_saves_outlines_shows_and_deletes_a_prompter_text(browser, viewport):
    ai, store = FakeAI(), InMemoryStore()
    app = create_app(Settings(developers=frozenset({DEV})), store=store, ai_client=ai)
    with running(app) as url:
        page = browser.new_page(viewport=viewport)
        page.on("dialog", lambda d: d.accept())
        open_prompter(page, url)
        assert "עוד אין טקסטים שמורים" in page.inner_text("#prompter")
        assert page.is_disabled("#pr-make-outline")                                  # an outline is made from a saved text

        page.fill("#pr-body", "Slide 1 — פתיחה\nבוקר טוב לכולם\nSlide 2 — סיכום\nתודה")
        page.reload()                                                                # what was typed is kept before a save
        page.wait_for_selector("#pr-form")
        assert page.input_value("#pr-body").startswith("Slide 1 — פתיחה")
        assert "עוד לא נשמר" in page.inner_text("#pr-msg")

        page.click("#pr-save")
        page.wait_for_selector("#pr-list li")
        assert page.inner_text("#pr-list li") .startswith("Slide 1 — פתיחה")         # the title is the first line
        assert len(store._prompter) == 1

        page.click("#pr-make-outline")
        page.wait_for_function("document.getElementById('pr-outline').value.includes('• בוקר טוב')")
        assert ai.calls[-1][0] == "outline"
        assert page.is_enabled("#pr-show-outline")

        page.click("#pr-show")                                                       # the full-screen prompter
        page.wait_for_selector(".mxp[role=dialog]")
        assert "בוקר טוב לכולם" in page.inner_text(".mxp")
        page.keyboard.press("Escape")
        page.wait_for_selector(".mxp", state="detached")

        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.click("#pr-delete")
        page.wait_for_selector("#pr-list", state="detached")
        assert store._prompter == {}


def test_a_failed_outline_says_why_and_keeps_the_text(browser):
    ai = FakeAI()
    ai.fail = "overloaded"
    app = create_app(Settings(developers=frozenset({DEV})), store=InMemoryStore(), ai_client=ai)
    with running(app) as url:
        page = browser.new_page(viewport=DESKTOP)
        open_prompter(page, url)
        page.fill("#pr-body", "שלום כיתה")
        page.click("#pr-save")
        page.wait_for_selector("#pr-list li")
        page.click("#pr-make-outline")
        page.wait_for_function("document.getElementById('pr-msg').classList.contains('error')")
        assert page.input_value("#pr-body") == "שלום כיתה"
