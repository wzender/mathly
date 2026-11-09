"""The card of lessons behind the curriculum on the home (add-behind-lessons-to-home 2.1), in a real browser."""
from datetime import datetime, timedelta, timezone

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.tests.serve import running
from mathly2.tests.test_home_browser import KID_ID, PHONE, bank, browser, no_sideways_scroll, sign_in, to_home, world  # noqa: F401

STAMP = "2026-10-05T10:00:00+00:00"


def seed(app, store, bank, lessons):
    today = clock.school_day()
    store.set_lesson_dates({lessons[0]: today - timedelta(days=2), lessons[1]: today - timedelta(days=9)})


def test_the_card_lists_the_lessons_behind_in_date_order_with_both_ways_to_finish(browser, bank):
    app, store, klass, lessons = world(bank)
    seed(app, store, bank, lessons)
    skills = [s["id"] for s in bank.skills if s["unit"] == lessons[0]]
    store.save_progress(KID_ID, skills[0], started_at=STAMP, mastered_at=STAMP)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#behind-card")
        rows = page.locator("#behind-card li")
        assert rows.count() == 2 and rows.nth(0).get_attribute("data-lesson") == lessons[1] and rows.nth(1).get_attribute("data-lesson") == lessons[0]     # the earlier date first
        assert "היה אמור להסתיים ב־" in rows.nth(0).inner_text()
        mine = page.locator(f"#behind-card li[data-lesson='{lessons[0]}']")
        assert f"1 מתוך {len(skills)}" in mine.locator("[data-way=skills]").inner_text() and mine.locator("[data-way=skills]").get_attribute("href") == f"#/skill/{skills[1]}"
        assert "לפחות 13 מתוך 15" in mine.locator("[data-way=quiz]").inner_text() and mine.locator("[data-way=quiz]").get_attribute("href") == f"#/quiz/{lessons[0]}"
        assert "עוד לא נעשה בוחן" in mine.locator("[data-best]").inner_text()
        no_sideways_scroll(page)
        assert not page.errors


def test_the_best_quiz_grade_shows_and_the_links_open_the_skill_and_the_quiz(browser, bank):
    app, store, klass, lessons = world(bank)
    seed(app, store, bank, lessons)
    q = store.create_attempt(KID_ID, "quiz", lessons[0], clock.now() - timedelta(hours=2), clock.now() - timedelta(hours=1), [])
    store.save_attempt(q["id"], submitted_at=clock.now() - timedelta(hours=1), grade=80)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#behind-card")
        assert "הציון הטוב ביותר בבוחן: 80" in page.inner_text(f"#behind-card li[data-lesson='{lessons[0]}'] [data-best]")
        page.click(f"#behind-card li[data-lesson='{lessons[1]}'] [data-way=skills]")
        page.wait_for_selector(".mx-sheet")
        assert page.evaluate("location.hash").startswith("#/skill/")


def test_no_card_when_no_lesson_is_behind_or_when_it_was_passed(browser, bank):
    app, store, klass, lessons = world(bank)
    store.set_lesson_dates({lessons[0]: clock.school_day() + timedelta(days=5)})
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#continue-path")
        assert page.locator("#behind-card").count() == 0
    app, store, klass, lessons = world(bank)
    store.set_lesson_dates({lessons[0]: clock.school_day() - timedelta(days=1)})
    q = store.create_attempt(KID_ID, "quiz", lessons[0], clock.now() - timedelta(hours=2), clock.now() - timedelta(hours=1), [])
    store.save_attempt(q["id"], submitted_at=clock.now() - timedelta(hours=1), grade=87)                   # 13 of 15: passed
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#continue-path")
        assert page.locator("#behind-card").count() == 0
