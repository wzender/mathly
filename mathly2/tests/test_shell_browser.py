import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.main import create_app
from mathly2.tests.serve import offline_formulas, running


def test_phone_shell_is_rtl_hebrew_and_does_not_scroll_sideways():
    with running(create_app()) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        page.goto(url)
        assert page.get_attribute("html", "dir") == "rtl"
        assert page.get_attribute("html", "lang") == "he"
        page.wait_for_selector("#signin")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()


def test_dollar_math_is_drawn_as_a_formula():
    with running(create_app()) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(url)
        page.wait_for_function("typeof (window.MathJax && window.MathJax.tex2svg) === 'function'", timeout=30000)
        page.evaluate("""async () => {
            const { fmt } = await import('/static/math.js');
            const box = document.createElement('p');
            box.id = 'probe';
            box.innerHTML = fmt('פתחו: $x² − 2x − 15$ ו־$(x + 3)(x − 5)$');
            document.body.append(box);
        }""")
        page.wait_for_selector("#probe span.m.m-img svg", timeout=10000)
        assert page.locator("#probe span.m.m-img").count() == 2
        assert page.get_attribute("#probe span.m.m-img >> nth=0", "aria-label") == "x² − 2x − 15"
        browser.close()


def test_dev_sign_in_then_sign_out():
    app = create_app(__import__("mathly2.config", fromlist=["Settings"]).Settings(teachers=frozenset({"t@school.test"})))
    with running(app) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        page.goto(url)
        page.wait_for_selector("#signin form#dev")           # signed out: only the sign-in screen
        assert "מיומנויות" not in page.inner_text("body")
        page.fill("#email", "kid@school.test")
        page.click("#dev button")
        page.wait_for_selector("#nav #out")
        assert page.inner_text("#nav").startswith("kid@school.test")
        page.click("#out")
        page.wait_for_selector("#signin")
        browser.close()


def test_student_not_in_a_class_sees_the_ask_your_teacher_message_with_their_email():
    with running(create_app()) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        page.goto(url)
        page.fill("#email", "new.kid@school.test")
        page.click("#dev button")
        page.wait_for_selector("#no-class")
        assert "new.kid@school.test" in page.inner_text("#no-class")
        assert "ממנהל הכיתות" in page.inner_text("#no-class")
        assert "מיומנויות" not in page.inner_text("body")
        browser.close()
