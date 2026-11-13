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


def test_practice_tests_below_87_are_inside_the_nearest_test_card_with_the_grade_in_the_button(browser, bank):
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
        page.wait_for_selector("#nearest-test #weak-tests")
        assert page.locator("#weak-tests").count() == 1 and page.locator("section#weak-tests").count() == 0           # inside the test's card, not a card of its own
        top, weak = page.locator("#nearest-test").bounding_box(), page.locator("#weak-tests").bounding_box()
        assert top["y"] <= weak["y"] and weak["y"] + weak["height"] <= top["y"] + top["height"]
        assert page.locator("#nearest-test .today").bounding_box()["y"] < weak["y"]                                    # under today's task
        rows = page.locator("#weak-tests li")
        assert rows.count() == 1 and rows.first.get_attribute("data-number") == "1"                                  # 87 is good enough
        link = rows.first.locator("[data-way=retake]")
        assert link.get_attribute("href") == f"#/exam/{test['id']}/1" and link.locator(".grade-chip").inner_text() == "25"
        assert "87" not in page.inner_text("#weak-tests") and "13" not in page.inner_text("#weak-tests")
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
