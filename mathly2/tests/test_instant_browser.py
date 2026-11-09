"""A screen opened again shows what it last knew (cache-and-instant-screens 2.1), in a real browser."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.tests.serve import running
from mathly2.tests.test_busy_browser import hold
from mathly2.tests.test_written_browser import (DESKTOP, KID, PHONE, TEACHER, bank, browser, day, jpeg, one_assignment, sign_in, teacher_work, world)  # noqa: F401


def counts(page):
    return page.eval_on_selector_all("#teacher-tabs [data-count]", "els => els.map(e => e.textContent)")


def test_going_back_to_a_tab_shows_its_content_and_numbers_at_once_then_the_fresh_ones(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = teacher_work(browser, url, tab="assignments")
        page.wait_for_function("[...document.querySelectorAll('#teacher-tabs [data-count]')].every(e => e.textContent)")
        known = counts(page)
        page.click("#teacher-tabs [data-tab='classes']")
        page.wait_for_selector("#teaching")
        held, release = hold(page, "**/api/teaching/**")
        page.click("#teacher-tabs [data-tab='assignments']")
        page.wait_for_selector("#work")                                      # drawn from memory while the server is still being asked
        assert held and counts(page) == known
        # something changes on the server meanwhile; once the answer arrives the fresh content replaces the remembered one
        other = store.create_assignment(row["class_id"], "משימה אחרת", day(7), TEACHER, "quiz", quiz_lesson=row["quiz_lesson"])
        release()
        page.wait_for_function("document.querySelectorAll('#work .assignment, #work article').length >= 2")
        assert not page.errors


def test_after_the_teachers_own_change_no_old_inbox_is_shown(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = teacher_work(browser, url, tab="assignments")
        page.click("#work [data-remove-assignment]")
        page.click("[data-confirm-remove-assignment]")
        page.wait_for_selector("#work")
        held, release = hold(page, "**/api/teaching/assignments")
        page.click("#teacher-tabs [data-tab='inbox']")
        page.click("#teacher-tabs [data-tab='assignments']")
        page.wait_for_timeout(300)
        assert not page.query_selector("#work .assignment[data-id], #work [data-remove-assignment]")   # nothing remembered of the removed one
        release()


def test_a_refresh_does_not_redraw_over_what_is_being_typed(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = teacher_work(browser, url, tab="assignments")
        page.click("#teacher-tabs [data-tab='classes']")
        page.wait_for_selector("#teaching")
        page.click("#teacher-tabs [data-tab='assignments']")
        page.wait_for_selector("#work")
        page.wait_for_timeout(500)
        held, release = hold(page, "**/api/teaching/**")
        page.click("#teacher-tabs [data-tab='classes']")
        page.click("#teacher-tabs [data-tab='assignments']")
        page.wait_for_selector("#work")
        store.create_assignment(row["class_id"], "משימה אחרת", day(7), TEACHER, "quiz", quiz_lesson=row["quiz_lesson"])
        page.click("#work summary")
        page.fill("#work .assignment-form input", "טיוטה")
        release()
        page.wait_for_timeout(500)
        assert page.input_value("#work .assignment-form input") == "טיוטה"
