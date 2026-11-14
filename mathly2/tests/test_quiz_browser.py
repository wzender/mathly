"""Lesson quizzes in a real browser: the trail node, the quiz sheet, the result, the grades screen (add-lesson-quizzes 3.1-3.4, 4.1)."""
import json
import uuid
from collections import Counter
from datetime import timedelta

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import attempts, clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, only, running

KID = "kid@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))
PHONE = {"width": 360, "height": 800}


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def lessons_of(bank, *sizes):
    counts = Counter(s["unit"] for s in bank.skills if bank.question_keys(s["id"]))
    return [next(l for l, c in counts.items() if c == size) for size in sizes]


def world(bank, lessons):
    store = InMemoryStore()
    store.add_member(store.create_class("setup", "A", lessons=list(lessons))["id"], KID)
    return create_app(Settings(), bank=only(bank, lessons), store=store), store


def seed_attempt(store, bank, lesson, grade=None, minutes_left=None, answers=None, n=15, seconds_left=None):
    """An attempt in the store: submitted with `grade`, or open with `minutes_left` (or `seconds_left`) on its clock; negative: overdue."""
    from mathly2 import quiz
    now = clock.now()
    drawn = quiz.draw(bank, lesson)[:n]
    if grade is None:
        left = timedelta(seconds=seconds_left) if seconds_left is not None else timedelta(minutes=45 if minutes_left is None else minutes_left)
        row = store.create_attempt(KID_ID, "quiz", lesson, now + left - timedelta(minutes=45), now + left, drawn)
    else:
        row = store.create_attempt(KID_ID, "quiz", lesson, now - timedelta(hours=1), now - timedelta(minutes=45), drawn)
        store.save_attempt(row["id"], submitted_at=now - timedelta(minutes=50), grade=grade)
    if answers:
        store.save_attempt(row["id"], answers=answers)
    return row


def path_page(browser, url, where="", viewport=PHONE):
    page = offline_formulas(browser.new_page(viewport=viewport))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + where)
    page.fill("#email", KID)
    page.click("#dev button")
    if not where:
        page.click(".subject-card")
        page.click(".tabs a[href='#/subject/math/path']")
        page.wait_for_selector(".orbit")
    page.errors = errors
    return page


def right(bank, ref, ok=True):
    q = bank._questions[ref["skill_id"]][ref["key"]]
    picks = [i for i, c in enumerate(q["choices"]) if bool(c.get("correct")) == ok]
    return (picks if ok else ([i for i in picks if q["choices"][i].get("mistake")] or picks))[0]


def tap_choice(page, bank, ref, ok=True):
    page.evaluate("window.MathlyBoard && (window.MathlyBoard.hasWork = () => true)")          # as if the way were on the board (board-work requires it; test_boardwork_browser tests that)
    page.click(f"#qz-choices .qz-choice[data-i='{right(bank, ref, ok)}']")


def refs_on_screen(store, lesson):
    return store.attempts_of(KID_ID, "quiz", lesson)[-1]["questions"]


# --- 3.1 the node ---

def test_every_lesson_has_a_quiz_node_with_its_state_in_words_and_it_is_a_keyboard_link(browser, bank):
    one, two, three = lessons_of(bank, 4, 3, 2)
    app, store = world(bank, [one, two, three])
    seed_attempt(store, bank, two, grade=85)                      # graded
    seed_attempt(store, bank, three, minutes_left=9)              # open
    with running(app) as url:
        page = path_page(browser, url)
        assert page.locator(".quiz-node").count() == 3
        text = lambda lesson: page.inner_text(f".quiz-node[data-quiz='{lesson}']")
        assert "○ עוד לא נעשה" in text(one) and "✓ הציון: 85" in text(two) and "◐ בוחן פתוח" in text(three)
        assert "בוחן" in page.get_attribute(f".quiz-node[data-quiz='{two}']", "aria-label") and "85" in page.get_attribute(f".quiz-node[data-quiz='{two}']", "aria-label")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.focus(f".quiz-node[data-quiz='{one}']")                  # reachable with the keyboard, opened with Enter
        assert page.evaluate("document.activeElement.dataset.quiz") == one
        page.keyboard.press("Enter")
        page.wait_for_selector(".mx-sheet #qz-q")
        assert page.locator("#path").count() == 1                     # the path is still under the sheet
    assert page.errors == []


# --- 3.2 the sheet ---

def test_the_quiz_opens_with_fifteen_questions_no_skill_names_and_no_countdown(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    with running(app) as url:
        page = path_page(browser, url)
        page.click(f".quiz-node[data-quiz='{lesson}']")
        page.wait_for_selector("#qz-q")
        assert page.evaluate("location.hash").startswith(f"#/quiz/{lesson}/")             # the address names the attempt
        assert "מתוך 15" in page.inner_text("#qz-count") and page.locator(".qz-dot").count() == 15
        sizes = page.eval_on_selector_all(".qz-dot", "els => els.map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })")
        assert all(w == h for w, h in sizes), sizes                                           # round, not tall ovals (the global button height once stretched them)
        assert page.locator("#qz-timer").count() == 0                                         # only the simulation is timed
        sheet = page.inner_text(".mx-sheet")
        assert not any(s["name"] in sheet for s in bank.skills if s["unit"] == lesson)
        assert page.locator(".qz-choice").count() >= 2 and page.locator(".qz-choice.right, .qz-choice.wrong").count() == 0


def test_a_choice_is_saved_on_the_server_survives_a_reload_and_shows_no_right_or_wrong(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    with running(app) as url:
        page = path_page(browser, url)
        page.click(f".quiz-node[data-quiz='{lesson}']")
        page.wait_for_selector("#qz-q")
        refs = refs_on_screen(store, lesson)
        key = page.get_attribute("#qz-q", "data-key")
        ref = next(r for r in refs if r["key"] == key)
        tap_choice(page, bank, ref, ok=False)
        assert page.locator(".qz-choice.picked").count() == 1 and page.get_attribute(".qz-choice.picked", "aria-pressed") == "true"
        assert page.locator("#qz-fb .ex-ok, #qz-fb .ex-bad").count() == 0                 # no feedback at all
        for _ in range(20):                                                                # the answer reached the server
            saved = store.attempts_of(KID_ID, "quiz", lesson)[-1]["answers"]
            if saved:
                break
            page.wait_for_timeout(100)
        assert saved == {key: right(bank, ref, ok=False)}
        before = store.attempts_of(KID_ID, "quiz", lesson)[-1]["id"]
        page.reload()
        page.wait_for_selector("#qz-q")                                                    # the same attempt
        assert store.attempts_of(KID_ID, "quiz", lesson)[-1]["id"] == before and len(store.attempts_of(KID_ID, "quiz", lesson)) == 1
        page.click(".qz-dot >> nth=0")
        assert page.locator(".qz-dot.done").count() == 1
        assert page.locator("#qz-timer").count() == 0


def test_the_board_and_calculator_are_available_in_a_quiz(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    with running(app) as url:
        page = path_page(browser, url)
        page.click(f".quiz-node[data-quiz='{lesson}']")
        page.wait_for_selector("#qz-q")
        page.wait_for_selector("[data-board-toggle]")
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board")
        page.click(".mx-board [data-do='calc']")
        page.wait_for_selector(".mx-calc", state="visible")
        assert page.locator(".mx-calc-keys button").count() > 10


def test_submitting_with_unanswered_questions_warns_first(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    with running(app) as url:
        page = path_page(browser, url)
        page.click(f".quiz-node[data-quiz='{lesson}']")
        page.wait_for_selector("#qz-q")
        ref = next(r for r in refs_on_screen(store, lesson) if r["key"] == page.get_attribute("#qz-q", "data-key"))
        tap_choice(page, bank, ref)
        page.click("#qz-submit")
        page.wait_for_selector("#qz-warn .ex-note")
        assert "14 שאלות בלי תשובה" in page.inner_text("#qz-warn")
        page.click("#qz-back")                                                             # back to the quiz: nothing was submitted
        assert page.locator("#qz-warn .ex-note").count() == 0 and store.attempts_of(KID_ID, "quiz", lesson)[-1]["submitted_at"] is None
        page.click("#qz-submit")
        page.click("#qz-yes")
        page.wait_for_selector("#qz-grade")
        assert store.attempts_of(KID_ID, "quiz", lesson)[-1]["submitted_at"] is not None


# --- 3.3 the result ---

def answers_for(bank, refs, rights):
    return {r["key"]: right(bank, r, ok) for r, ok in zip(refs, rights)}


def test_the_result_shows_the_grade_the_lost_skill_with_its_link_and_the_mistakes_but_no_right_answers(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    row = seed_attempt(store, bank, lesson)
    refs = row["questions"]
    by_skill = Counter(r["skill_id"] for r in refs)
    lost_skill = next(s for s, n in by_skill.items() if n >= 2)
    missed = [r for r in refs if r["skill_id"] == lost_skill][:2]
    rights = [r not in missed for r in refs]
    store.save_attempt(row["id"], answers=answers_for(bank, refs, rights))
    with running(app) as url:
        page = path_page(browser, url, f"#/quiz/{lesson}/{row['id']}")
        page.wait_for_selector("#qz-q")
        page.click("#qz-submit")
        page.wait_for_selector("#qz-grade")
        assert page.inner_text("#qz-grade b") == "87" and "13 תשובות נכונות מתוך 15" in page.inner_text(".qz-result")
        page.wait_for_function("document.querySelector('#qz-best').innerText.includes('87')")        # the lesson's grade
        link = page.locator("#qz-lost a")
        assert link.count() == 1 and link.get_attribute("href") == f"#/skill/{lost_skill}" and "2 שאלות שגויות" in page.inner_text("#qz-lost")
        assert page.locator("#qz-missed li").count() == 2
        for item in range(2):
            ref = missed[item]
            mistake = bank.grade(ref["skill_id"], ref["key"], right(bank, ref, ok=False))["mistake"]
            if mistake:
                assert mistake["name"] in page.inner_text("#qz-missed")
        text = page.inner_text(".mx-sheet")
        for ref in missed:                                                                        # a right choice is never written on the page
            question = bank._questions[ref["skill_id"]][ref["key"]]
            correct = next(c["text"] for c in question["choices"] if c.get("correct"))
            if len(correct) > 3 and correct not in question["question"] and correct != question["choices"][right(bank, ref, ok=False)]["text"]:
                assert correct not in text
        assert page.locator(".right, [data-correct], .ex-ok").count() == 0
        page.click("#qz-lost a")                                                                    # the link opens the skill over the path
        page.wait_for_selector("#ex-q")
        assert page.locator("#qz-grade").count() == 0


def test_a_quiz_started_long_ago_is_still_open_with_its_answers(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    row = seed_attempt(store, bank, lesson, minutes_left=-5)                                     # its stored due_at passed five minutes ago
    store.save_attempt(row["id"], answers=answers_for(bank, row["questions"], [True] * 6))
    with running(app) as url:
        page = path_page(browser, url, f"#/quiz/{lesson}/{row['id']}")
        page.wait_for_selector("#qz-q")
        assert page.locator(".qz-dot.done").count() == 6 and page.locator("#qz-timer").count() == 0
        page.wait_for_timeout(1500)
        assert page.locator("#qz-grade").count() == 0                                             # nothing hands it in


def test_a_retake_draws_new_questions_and_a_second_quiz_does_not_replace_the_best_grade(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    first = seed_attempt(store, bank, lesson, grade=85)
    with running(app) as url:
        page = path_page(browser, url, f"#/quiz/{lesson}")                                          # the node's address starts a quiz
        page.wait_for_selector("#qz-q")
        second = store.attempts_of(KID_ID, "quiz", lesson)[-1]
        assert second["id"] != first["id"] and not {q["key"] for q in second["questions"]} & {q["key"] for q in first["questions"]}
        page.click("#qz-submit")
        page.click("#qz-yes")                                                                      # an empty quiz: 0
        page.wait_for_selector("#qz-grade")
        assert page.inner_text("#qz-grade b") == "0"
        page.wait_for_function("document.querySelector('#qz-best').innerText.includes('85')")      # the best grade stays
        page.click("#qz-retake")
        page.wait_for_selector("#qz-q")
        third = store.attempts_of(KID_ID, "quiz", lesson)[-1]
        used = {q["key"] for a in (first, second) for q in a["questions"]}
        assert third["id"] not in (first["id"], second["id"]) and len(third["questions"]) == 15
        assert len({q["key"] for q in third["questions"]} & used) <= 5                              # mostly new questions


# --- 3.4 the grades screen ---

def test_the_grades_screen_is_empty_at_first_then_lists_the_best_grade_attempts_and_date(browser, bank):
    one, two = lessons_of(bank, 4, 3)
    app, store = world(bank, [one, two])
    with running(app) as url:
        page = path_page(browser, url, "#/grades")
        page.wait_for_selector("#grades")
        assert "עוד אין ציונים" in page.inner_text("#no-grades") and page.locator("#quiz-grades").count() == 0
        seed_attempt(store, bank, one, grade=60)
        seed_attempt(store, bank, one, grade=85)                                                    # the better of two
        seed_attempt(store, bank, one, grade=70)
        seed_attempt(store, bank, two, grade=40)
        page.reload()
        page.wait_for_selector("#quiz-grades")
        row = page.locator(f"#quiz-grades li[data-lesson='{one}']")
        assert row.locator(".gr-num").inner_text() == "85" and "3 ניסיונות" in row.inner_text() and "האחרון ב" in row.inner_text()
        assert row.locator("[role=progressbar]").get_attribute("aria-valuenow") == "85"
        assert page.locator(f"#quiz-grades li[data-lesson='{two}'] .gr-num").inner_text() == "40"
        assert page.locator("#quiz-grades li").count() == 2
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.locator(".tabs a[aria-current='page']").inner_text() == "ציונים"
        page.click(f"#quiz-grades li[data-lesson='{one}'] a")                                      # a row leads to that lesson's quiz
        page.wait_for_selector("#qz-q")


# --- 4.1 the whole quiz ---

def test_a_whole_quiz_from_the_trail_to_the_grades_screen(browser, bank):
    (lesson,) = lessons_of(bank, 4)
    app, store = world(bank, [lesson])
    with running(app) as url:
        page = path_page(browser, url)
        page.click(f".quiz-node[data-quiz='{lesson}']")
        page.wait_for_selector("#qz-q")
        refs = refs_on_screen(store, lesson)
        by_skill = Counter(r["skill_id"] for r in refs)
        lost_skill = next(s for s, n in by_skill.items() if n >= 2)
        wrong = {r["key"] for r in [r for r in refs if r["skill_id"] == lost_skill][:2]}
        for _ in range(15):                                                                           # answer all fifteen, moving with "next"
            ref = next(r for r in refs if r["key"] == page.get_attribute("#qz-q", "data-key"))
            tap_choice(page, bank, ref, ok=ref["key"] not in wrong)
            if page.locator("#qz-count").inner_text().startswith("שאלה 15"):
                break
            page.click(".qz-nav button >> nth=1")
            page.wait_for_function("(k) => document.querySelector('#qz-q').dataset.key !== k", arg=ref["key"])
        page.wait_for_function("document.querySelectorAll('.qz-dot.done').length === 15")
        page.click("#qz-submit")                                                                      # all answered: no warning
        page.wait_for_selector("#qz-grade")
        assert page.inner_text("#qz-grade b") == "87"
        assert page.locator("#qz-lost a").get_attribute("href") == f"#/skill/{lost_skill}"
        page.click("#qz-lost a")                                                                      # practice the weak skill
        page.wait_for_selector("#ex-q")
        page.click(".mx-x")
        page.wait_for_selector(f".quiz-node[data-quiz='{lesson}'].graded")
        assert "✓ הציון: 87" in page.inner_text(f".quiz-node[data-quiz='{lesson}']")                 # the node shows the grade
        page.click(".tabs a[href='#/grades']")
        page.wait_for_selector("#quiz-grades")
        assert page.locator(f"#quiz-grades li[data-lesson='{lesson}'] .gr-num").inner_text() == "87"
