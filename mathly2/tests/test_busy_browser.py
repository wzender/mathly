"""A button whose action takes time shows it (work-tabs-and-hints 1.1), in a real browser."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_written_browser import (DESKTOP, KID, PHONE, TEACHER, bank, browser, day, jpeg, one_assignment, sign_in, teacher_work, world)  # noqa: F401

OBSERVER = """
window.__everBusy = false;
new MutationObserver(() => { if (document.querySelector('.busy')) window.__everBusy = true; }).observe(document, { subtree: true, attributes: true, attributeFilter: ['class'] });
"""


def hold(page, pattern):
    """Hold every request that matches until `release()`; returns (held list, release function)."""
    held = []
    page.route(pattern, lambda route: held.append(route))
    return held, lambda: [r.continue_() for r in list(held)] and held.clear()


def test_a_plain_button_shows_a_spinner_after_a_moment_ignores_a_second_press_and_clears_after_success(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#answer")
        page.set_input_files("[data-file=upload]", files=[{"name": "a.jpg", "mimeType": "image/jpeg", "buffer": jpeg()}])
        page.wait_for_selector("#draft li[data-picture-id]")
        held, release = hold(page, "**/api/assignments/*/submission")
        page.click("#hand-in")
        page.wait_for_selector("#hand-in.busy")                                                # after about a third of a second
        assert page.get_attribute("#hand-in", "aria-busy") == "true"
        page.click("#hand-in", force=True)                                                     # a second press does nothing
        page.wait_for_timeout(300)
        assert len(held) == 1
        release()
        page.wait_for_selector("#assignment[data-state='handed_in']")
        assert page.locator(".busy").count() == 0


def test_a_forms_submit_button_shows_it_too_and_a_quick_action_never_does(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=DESKTOP))
        page.add_init_script(OBSERVER)
        page.goto(url)
        page.fill("#email", TEACHER)
        page.click("#dev button")
        page.wait_for_selector("#teaching")
        page.click("#teacher-tabs [data-tab='tests']")
        page.wait_for_selector("#tests")
        page.click(".set-test summary")
        page.fill("[name=date]", day(10).isoformat())
        held, release = hold(page, "**/api/classes/*/tests")
        page.click(".set-test button[type=submit]")
        page.wait_for_selector(".set-test button[type=submit].busy")
        release()
        page.wait_for_selector(".test-row")
        assert page.locator(".busy").count() == 0
        page.evaluate("window.__everBusy = false")                                              # a quick action: the button never turns busy
        page.click("#teacher-tabs [data-tab='classes']")
        page.wait_for_selector("#teaching")
        page.click("#teacher-tabs [data-tab='tests']")
        page.wait_for_selector("#tests")
        assert page.evaluate("window.__everBusy") is False


def test_a_picture_upload_from_a_file_chooser_marks_its_button(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#answer")
        held, release = hold(page, "**/api/pictures")
        page.set_input_files("[data-file=upload]", files=[{"name": "a.jpg", "mimeType": "image/jpeg", "buffer": jpeg()}])
        page.wait_for_selector("label.file.busy")
        release()
        page.wait_for_selector("#draft li[data-picture-id]")
        assert page.locator("label.file.busy").count() == 0


def test_with_reduced_motion_the_button_shows_dots_and_nothing_turns(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}", reduced_motion="reduce")
        page.wait_for_selector("#answer")
        page.set_input_files("[data-file=upload]", files=[{"name": "a.jpg", "mimeType": "image/jpeg", "buffer": jpeg()}])
        page.wait_for_selector("#draft li[data-picture-id]")
        held, release = hold(page, "**/api/assignments/*/submission")
        page.click("#hand-in")
        page.wait_for_selector("#hand-in.busy")
        assert page.evaluate("getComputedStyle(document.querySelector('#hand-in'), '::after').content") == '"…"'
        assert page.evaluate("document.getAnimations().filter(a => a.animationName === 'ex-spin').length") == 0
        release()
        page.wait_for_selector("#assignment[data-state='handed_in']")


def test_the_state_clears_after_an_error_and_the_exercise_choices_keep_their_own_indicator(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#answer")
        page.set_input_files("[data-file=upload]", files=[{"name": "a.jpg", "mimeType": "image/jpeg", "buffer": jpeg()}])
        page.wait_for_selector("#draft li[data-picture-id]")
        held = []
        page.route("**/api/assignments/*/submission", lambda route: held.append(route))
        page.click("#hand-in")
        page.wait_for_selector("#hand-in.busy")
        held[0].fulfill(status=500, body='{"detail": "x"}', content_type="application/json")
        page.wait_for_selector("#add-error:not([hidden])")
        assert page.locator(".busy").count() == 0 and not page.is_disabled("#hand-in")
