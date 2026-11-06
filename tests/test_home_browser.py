"""Home and path tabs (openspec student-home-and-exam-quizzes): home shows only what has a date or needs the student,
the path tab holds the self-paced learning, and a class teacher keeps their classes."""
from datetime import date, datetime, timedelta, timezone

import pytest

from test_exam_prep_browser import ExamAuth, exam_server, with_progress   # noqa: F401 (a fixture)
from test_focus_browser import DANA, TEACHER, session

playwright = pytest.importorskip("playwright.sync_api")

COMMENT = {"attempt_id": "a1", "question": "פילוג מורחב", "score": 80, "question_id": "t_ext"}


def days_from_now(n):
    return (date.today() + timedelta(days=n)).isoformat()


def to_math(page):
    """With exams the app asks for the subject first; without, it goes straight to math."""
    page.locator('[data-subject="מתמטיקה"], #mathView .mx-top').first.wait_for()
    if page.locator('[data-subject="מתמטיקה"]').count():
        page.locator('[data-subject="מתמטיקה"]').click()


def open_home(browser, url, comments=()):
    page, errors = session(browser, DANA)
    page.route("**/api/math/teacher-comments", lambda route: route.fulfill(json={"comments": list(comments)}))

    def me(route):   # comments are loaded only where answer scans are on
        reply = route.fetch()
        route.fulfill(response=reply, json={**reply.json(), "answer_scans": True})
    page.route("**/api/me", me)
    page.goto(url)
    to_math(page)
    return page, errors


def test_home_shows_what_is_due_in_order_and_no_trail(exam_server):
    url, auth = exam_server
    auth.exams = [{"subject": "מתמטיקה", "date": days_from_now(5), "units": ["t"], "note": ""}]
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_home(browser, url, [COMMENT])
            nav = page.locator(".mx-nav button")
            playwright.expect(nav.locator("span")).to_have_text(["בית", "מסלול", "ציונים", "האוסף"])
            playwright.expect(page.locator('.mx-nav [data-view="home"]')).to_have_attribute("aria-current", "page")
            home = page.locator(".mx-home")
            exam = home.locator(".mx-home-exam")
            playwright.expect(exam).to_contain_text("מבחן במתמטיקה")
            playwright.expect(exam).to_contain_text("עוד 5 ימים")
            playwright.expect(page.locator(".mx-teacher-comment")).to_contain_text("פילוג מורחב")
            playwright.expect(page.locator(".mx-continue")).to_be_visible()
            # the order: exam, quizzes, due work, comments, then the way to the path
            order = page.evaluate("""() => [...document.querySelector('.mx-home').children].map(el =>
                el.matches('.mx-home-exam') ? 'exam' : el.matches('.mx-hq') ? 'quiz'
                : el.matches('.mx-tasks-sum, .mx-grades-btn, .mx-asgs') ? 'due' : el.matches('.mx-teacher-comment') ? 'comment'
                : el.matches('.mx-continue') ? 'continue' : el.className)""")
            assert order.index("exam") < order.index("quiz") < order.index("due") < order.index("comment") < order.index("continue"), order
            # nothing of the path on home
            for sel in (".mx-trail", ".mx-daily", ".mx-review", ".mx-patterns"):
                playwright.expect(page.locator(sel)).to_have_count(0)
            # the exam opens its preparation
            exam.click()
            playwright.expect(page.locator(".mx-prep-sheet #mxTitle")).to_have_text("הכנה למבחן במתמטיקה")
            assert not errors, errors
        finally:
            browser.close()


def test_seen_comments_are_not_on_home_and_an_exam_without_units_has_no_preparation(exam_server):
    url, auth = exam_server
    auth.exams = [{"subject": "מתמטיקה", "date": days_from_now(9)}]
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_home(browser, url)
            exam = page.locator(".mx-home-exam")
            playwright.expect(exam).to_contain_text("עוד 9 ימים")
            playwright.expect(exam.locator("[data-prep]")).to_have_count(0)
            assert exam.evaluate("el => el.tagName") == "DIV"   # nothing to open
            playwright.expect(page.locator(".mx-teacher-comment")).to_have_count(0)
            assert not errors, errors
        finally:
            browser.close()


def open_questions_only(route):
    """The skills with no multiple-choice question: no quiz can be offered."""
    graph = route.fetch().json()
    for skill in graph["skills"]:
        for q in skill.get("questions", []):
            q.pop("choices", None)
    route.fulfill(json=graph)


def test_home_is_never_empty_and_continue_opens_the_path_at_the_next_topic(exam_server):
    url, auth = exam_server
    auth.exams = []   # no exam, no quiz, nothing due
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, DANA)
            page.route("**/api/math/skills", open_questions_only)
            page.goto(url)
            to_math(page)
            playwright.expect(page.locator(".mx-home-empty")).to_have_text("אין כרגע משהו להגיש או מבחן קרוב.")
            playwright.expect(page.locator(".mx-continue")).to_be_visible()
            assert not errors, errors
        finally:
            browser.close()
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_home(browser, url)
            playwright.expect(page.locator(".mx-home-empty")).to_have_count(0)   # a quiz is offered
            page.locator(".mx-continue").click()
            playwright.expect(page.locator('.mx-nav [data-view="path"]')).to_have_attribute("aria-current", "page")
            playwright.expect(page.locator(".mx-star.st-next")).to_be_in_viewport()
            assert not errors, errors
        finally:
            browser.close()


def ago(days):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_the_path_tab_holds_review_and_the_collection_jumps_to_a_unit(exam_server):
    url, auth = exam_server
    auth.exams = []
    old = ago(30)
    due = {"t_ext": old, "t_simplify": old, "t_ext_eq": old}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, DANA)
            with_progress(page, {"done": due, "seen": due, "review": {k: {"box": 0, "due": "2020-01-01"} for k in due}, "updated": 1})
            page.goto(url)
            to_math(page)
            playwright.expect(page.locator(".mx-review")).to_have_count(0)   # not on home
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator(".mx-review")).to_be_visible()
            playwright.expect(page.locator(".mx-daily")).to_be_visible()
            # path order: daily goal, review, then the trail
            order = page.evaluate("""() => ['.mx-daily', '.mx-review', '.mx-trail'].map(s =>
                [...document.querySelectorAll('#mathView *')].indexOf(document.querySelector(s)))""")
            assert order == sorted(order) and -1 not in order, order
            page.locator('.mx-nav [data-view="sky"]').click()
            page.locator('.mx-con-card[data-unit="k"]').click()
            playwright.expect(page.locator('.mx-nav [data-view="path"]')).to_have_attribute("aria-current", "page")
            playwright.expect(page.locator("#mx-unit-k")).to_be_in_viewport()
            assert not errors, errors
        finally:
            browser.close()


def test_a_class_teacher_keeps_the_classes_and_has_no_path_tab(exam_server):
    url, auth = exam_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = session(browser, TEACHER)
            page.goto(url)
            to_math(page)
            playwright.expect(page.locator(".mx-classes")).to_be_visible()
            playwright.expect(page.locator('.mx-nav [data-view="path"]')).to_have_count(0)
            # the student preview has both tabs
            page.locator(".mx-myclass").first.click()
            page.locator('[data-act="preview-on"]').click()
            to_math(page)
            playwright.expect(page.locator('.mx-nav [data-view="path"]')).to_have_count(1)
            playwright.expect(page.locator(".mx-continue")).to_be_visible()
            assert not errors, errors
        finally:
            browser.close()
