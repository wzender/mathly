"""The work on the board in a real browser: a quiz asks for the way before a choice, the board goes with the answer, and the teacher gives
points for the way (board-work 2.1-2.3)."""
import time
import uuid

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_home_browser import KID, PHONE, TEACHER, sign_in, teacher_page

KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def draw_line(page):
    box = page.locator(".mx-board canvas").bounding_box()
    x, y = box["x"] + 60, box["y"] + 160
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + 60, y + 30, steps=5)
    page.mouse.move(x + 120, y + 60, steps=5)
    page.mouse.up()


def wait_until(check, seconds=10):
    end = time.time() + seconds
    while time.time() < end:
        if check():
            return
        time.sleep(0.1)
    raise AssertionError("timed out")


def test_a_quiz_asks_for_the_way_first_and_the_teacher_gives_points_for_it(browser, bank):
    lesson = next(l["id"] for l in bank.lessons if any(s["unit"] == l["id"] and bank.question_keys(s["id"]) for s in bank.skills))
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=[lesson], teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    app = create_app(Settings(teachers=frozenset({TEACHER})), bank=bank, store=store)
    with running(app) as url:
        page = sign_in(browser, url, f"#/quiz/{lesson}")
        page.wait_for_selector("#qz-q")
        page.locator(".qz-choice").first.click()
        page.wait_for_selector("#qz-need-work")
        assert page.locator(".qz-choice.picked").count() == 0                                   # no choice without the way
        page.click("#qz-open-board")
        page.wait_for_selector(".mx-board.full canvas")
        draw_line(page)
        page.click(".mx-board .mx-board-back")
        page.locator(".qz-choice").first.click()
        page.wait_for_selector(".qz-choice.picked")
        attempt = store.attempts_of(KID_ID, "quiz")[0]
        key = attempt["questions"][0]["key"]
        wait_until(lambda: key in store.work_of(KID_ID, attempt["id"]))                        # the board went with the answer
        page.click("#qz-submit")
        page.click("#qz-yes")
        page.wait_for_selector("#qz-grade")
        assert page.errors == []

        teacher = teacher_page(browser, url)
        teacher.click("#teacher-tabs [data-tab='work']")
        teacher.wait_for_selector(f".work-list li[data-attempt='{attempt['id']}']")
        assert "לבדיקה" in teacher.inner_text(".work-list li")
        teacher.click(f"[data-open='{attempt['id']}']")
        teacher.wait_for_selector(f".work-q[data-key='{key}'] img.work-pic:not([hidden])")      # the student's board, through the server
        assert teacher.locator(".work-q .no-work").count() == len(attempt["questions"]) - 1
        before = int(teacher.inner_text("#work-grade"))
        second = attempt["questions"][1]["key"]                                                  # not answered: half the points for the way
        teacher.click(f".work-q[data-key='{second}'] [data-points='0.5']")
        teacher.click("#work-save")
        teacher.wait_for_selector("#work-check .ex-note")
        after = int(teacher.inner_text("#work-grade"))
        assert after > before and store.get_attempt(attempt["id"])["credit"] == {second: 0.5}
        teacher.click("#work-back")
        teacher.wait_for_selector(".work-list li")
        assert "נבדק" in teacher.inner_text(".work-list li")
        assert teacher.errors == []


def test_a_lesson_round_needs_no_board_but_sends_it_when_there_is_one(browser, bank):
    lesson = next(l["id"] for l in bank.lessons if any(s["unit"] == l["id"] and bank.question_keys(s["id"]) for s in bank.skills))
    store = InMemoryStore()
    store.add_member(store.create_class("setup", "A", lessons=[lesson], teacher_email=TEACHER)["id"], KID)
    with running(create_app(Settings(), bank=bank, store=store)) as url:
        page = sign_in(browser, url, f"#/round/{lesson}")
        page.wait_for_selector(".round-layer #ex-q")
        page.locator(".ex-choice").first.click()                                                  # no board: the answer goes through
        page.wait_for_selector(".ex-ok, .ex-bad")
        page.click("#rd-next")
        page.wait_for_function("document.querySelector('#rd-count').textContent.includes('2 מתוך')")
        key = page.locator("#ex-q").get_attribute("data-key")
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board.full canvas")
        draw_line(page)
        page.click(".mx-board .mx-board-back")
        page.locator(".ex-choice").first.click()
        page.wait_for_selector(".ex-ok, .ex-bad")
        rnd = store.attempts_of(KID_ID, "lesson_round")[0]
        wait_until(lambda: key in store.work_of(KID_ID, rnd["id"]))
        assert len(store.work_of(KID_ID, rnd["id"])) == 1                                          # the first answer had no board
        assert page.errors == []


def test_after_a_practice_test_the_student_sees_the_review_of_the_way(browser, bank):
    from datetime import timedelta
    from mathly2 import boardreview, clock
    from mathly2.tests.test_boardreview_api import FakeReviewer
    lessons = [l["id"] for l in bank.lessons][:2]
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=lessons, teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    test = store.create_test(klass["id"], clock.school_day() + timedelta(days=9), lessons, TEACHER, created_at=clock.now() - timedelta(days=20))
    app = create_app(Settings(), bank=bank, store=store, reviewer=FakeReviewer())
    with running(app) as url:
        page = sign_in(browser, url, f"#/exam/{test['id']}/1/all")
        page.wait_for_selector("#qz-q")
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board.full canvas")
        draw_line(page)
        page.click(".mx-board .mx-board-back")
        page.locator(".qz-choice").first.click()
        page.wait_for_selector(".qz-choice.picked")
        page.click("#qz-submit")
        page.click("#qz-yes")
        page.wait_for_selector("#qz-review[data-state='done']", timeout=15000)                   # pending at first, then the review
        text = page.inner_text("#qz-review")
        assert "משוב על הדרך" in text and "שאלה 1" in text and "חלק מהדרך נכון" in text and "בדקו סימן" in text
        assert page.errors == []
