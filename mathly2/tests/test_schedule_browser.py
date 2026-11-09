"""The curriculum and the lesson marks (add-lesson-schedule 2.2, 3.2), in a real browser."""
from datetime import timedelta

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.tests.serve import offline_formulas, only, running
from mathly2.tests.test_foundation_screens_browser import MGR, PHONE, browser, no_sideways_scroll, page_for, seeded, sign_in  # noqa: F401
from mathly2.tests.test_path_browser import KID, KID_ID, NOW, bank, lessons_by_size, path_page, world  # noqa: F401


def test_a_manager_sets_dates_and_they_are_shown_again_without_sideways_scroll(browser):
    app, store = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, MGR)
        page.click("#mgr-tabs [data-tab=curriculum]")
        page.wait_for_selector("#curriculum-form")
        assert page.locator("#curriculum-form input[type=date]").count() == 24
        no_sideways_scroll(page)
        page.fill("#due-t", "2026-11-03")
        page.fill("#due-t2", "2026-12-01")
        page.click("#save-curriculum")
        page.wait_for_selector("#msg")
        assert page.input_value("#due-t") == "2026-11-03" and page.input_value("#due-t2") == "2026-12-01"
        assert store.curriculum() == {"t": __import__("datetime").date(2026, 11, 3), "t2": __import__("datetime").date(2026, 12, 1)}
        page.fill("#due-t2", "")
        page.click("#save-curriculum")
        page.wait_for_selector("#msg")
        assert page.input_value("#due-t2") == "" and list(store.curriculum()) == ["t"]


def test_the_path_marks_a_behind_lesson_a_completed_one_and_leaves_the_rest_alone(browser, bank):
    two, three, six = lessons_by_size(bank)
    app, store = world(bank, [two, three, six])
    today = clock.school_day()
    store.set_lesson_dates({two: today - timedelta(days=3), three: today - timedelta(days=3), six: today + timedelta(days=9)})
    for skill in (s["id"] for s in bank.skills if s["unit"] == three):
        store.save_progress(KID_ID, skill, started_at=NOW, mastered_at=NOW)
    with running(app) as url:
        page = path_page(browser, url)
        behind = page.locator(f"#lesson-{two} [data-status=behind]")
        assert behind.count() == 1 and "היה אמור להסתיים ב־" in behind.inner_text()       # said in words, with the date
        assert page.locator(f"#lesson-{three} [data-status=completed]").inner_text().count("הושלם") == 1
        assert page.locator(f"#lesson-{three} [data-status=behind]").count() == 0
        assert page.locator(f"#lesson-{six} [data-status]").count() == 0                   # a date still ahead: no mark
        assert "שיעור אחד בפיגור" in page.inner_text("#behind-note")
        assert page.locator(".star[href]").count() == page.locator(".star").count()        # nothing is locked
        no_sideways_scroll(page)


def test_no_dates_no_marks(browser, bank):
    two, three, _ = lessons_by_size(bank)
    app, _ = world(bank, [two, three])
    with running(app) as url:
        page = path_page(browser, url)
        assert page.locator("[data-status]").count() == 0 and page.locator("#behind-note").count() == 0
