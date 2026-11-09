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


def test_the_card_lists_the_lessons_behind_in_date_order_each_with_only_the_quiz_link(browser, bank):
    app, store, klass, lessons = world(bank)
    seed(app, store, bank, lessons)
    q = store.create_attempt(KID_ID, "quiz", lessons[0], clock.now() - timedelta(hours=2), clock.now() - timedelta(hours=1), [])
    store.save_attempt(q["id"], submitted_at=clock.now() - timedelta(hours=1), grade=80)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#behind-card")
        rows = page.locator("#behind-card li")
        assert rows.count() == 2 and rows.nth(0).get_attribute("data-lesson") == lessons[1] and rows.nth(1).get_attribute("data-lesson") == lessons[0]     # the earlier date first
        assert page.locator("#behind-card [data-way=skills]").count() == 0 and page.locator("#behind-card a").count() == 2                                 # only the quiz links
        mine = page.locator(f"#behind-card li[data-lesson='{lessons[0]}']")
        assert mine.locator("[data-way=quiz]").inner_text() == "בוחן" and mine.locator("[data-way=quiz]").get_attribute("href") == f"#/quiz/{lessons[0]}"
        assert mine.locator("[data-best]").inner_text() == "80" and rows.nth(0).locator("[data-best]").inner_text() == "-"          # a bare grade, or a dash
        assert "13" not in page.inner_text("#behind-card") and "מתוך" not in page.inner_text("#behind-card")                       # nothing explains the pass line
        assert "⚠" in mine.inner_text() and "מיומנויות" not in page.inner_text("#behind-card")
        no_sideways_scroll(page)
        assert not page.errors


def test_the_quiz_link_opens_the_quiz(browser, bank):
    app, store, klass, lessons = world(bank)
    seed(app, store, bank, lessons)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#behind-card")
        page.click(f"#behind-card li[data-lesson='{lessons[1]}'] [data-way=quiz]")
        page.wait_for_selector("#qz-q")
        assert page.evaluate("location.hash").startswith(f"#/quiz/{lessons[1]}/")


def test_practice_tests_below_87_are_listed_with_a_retake_link_and_others_are_not(browser, bank):
    app, store, klass, lessons = world(bank)
    test = store.create_test(klass["id"], clock.school_day() + timedelta(days=10), lessons[:1], "t@school.test", created_at=clock.now() - timedelta(days=20))
    for skill in [x["id"] for x in bank.skills if x["unit"] == lessons[0]][:2]:                                   # started skills, so a practice test can begin
        store.save_progress(KID_ID, skill, started_at=STAMP)
    for number, grade in ((1, 25), (2, 87)):
        row = store.create_attempt(KID_ID, "exercise_test", f"{test['id']}:{number}", clock.now() - timedelta(hours=2), clock.now() - timedelta(hours=1), [])
        store.save_attempt(row["id"], submitted_at=clock.now() - timedelta(hours=1), grade=grade)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#weak-tests")
        rows = page.locator("#weak-tests li")
        assert rows.count() == 1 and rows.first.get_attribute("data-number") == "1"                                  # 87 is good enough
        assert rows.first.locator("[data-best]").inner_text() == "25" and "87" not in page.inner_text("#weak-tests") and "13" not in page.inner_text("#weak-tests")
        assert rows.first.locator("[data-way=retake]").get_attribute("href") == f"#/exam/{test['id']}/1"
        no_sideways_scroll(page)
        page.click("#weak-tests [data-way=retake]")
        page.wait_for_selector("#qz-q")
        assert not page.errors


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
