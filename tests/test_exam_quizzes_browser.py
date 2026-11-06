"""The quizzes chosen for each student before an exam (openspec student-home-and-exam-quizzes): two strengthening
quizzes with feedback after each answer, a quiz like the exam with feedback at the end, retakes with new questions and
the best grade."""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from test_exam_prep_browser import exam_server, with_progress   # noqa: F401 (a fixture)
from test_focus_browser import DANA, session
from test_home_browser import to_math

playwright = pytest.importorskip("playwright.sync_api")

T = ["t_ext", "t_simplify", "t_ext_eq", "t_area", "t_formulas"]
K = ["k_def", "k_angles", "k_diag", "k_axes"]
EXAMPLE = {"question": "פתחו: $(x + 1)(x + 2)$", "steps": [{"do": "כופלים כל איבר", "why": "חוק הפילוג"}], "answer": "$x² + 3x + 2$"}


def recent():
    return (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()


def practised(skills=T + K, quizzes=()):
    """Every skill answered 8 times; the first three of t not finished, the rest finished."""
    at = recent()
    return {"tries": {s: 8 for s in skills}, "wrongs": {s: 3 for s in skills[:3]}, "seen": {s: at for s in skills},
            "done": {s: at for s in skills[3:]}, "quizzes": list(quizzes), "updated": 1}


def exam_in(auth, days, units=("t", "k")):
    when = (date.today() + timedelta(days=days)).isoformat()
    auth.exams = [{"subject": "מתמטיקה", "date": when, "units": list(units), "note": ""}]
    return f"3|מתמטיקה|{when}"


def with_examples(route):
    graph = route.fetch().json()
    for skill in graph["skills"]:
        skill["example"] = EXAMPLE
    route.fulfill(json=graph)


def open_app(browser, url, progress):
    page, errors = session(browser, DANA)
    page.route("**/api/math/skills", with_examples)
    with_progress(page, progress)
    page.goto(url)
    to_math(page)
    return page, errors


def stored(page):
    return page.evaluate("""() => { const k = Object.keys(localStorage).find(k => k.startsWith('mathly.progress.v1:'));
        return JSON.parse(localStorage.getItem(k)); }""")


def answer_all(page, right=True, sure=None):
    sheet = page.locator(".mx-quiz-sheet")
    n = sheet.locator(".mx-quiz-dots button").count()
    for i in range(n):
        sheet.locator(".mx-choices button[data-right]" if right else ".mx-choices button:not([data-right])").first.click()
        if sure is not None:
            sheet.locator(f'[data-quiz-sure="{sure}"]').click()
        sheet.locator("[data-act=quiz-submit]" if i == n - 1 else "[data-act=quiz-next]").click()
    return n


def test_three_quizzes_six_days_before_and_two_ten_days_before(exam_server):
    url, auth = exam_server
    exam_in(auth, 6)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            cards = page.locator(".mx-hq .mx-hq-card")
            playwright.expect(cards.locator("b")).to_have_text(["מבחן תרגול 1", "מבחן תרגול 2", "מבחן תרגול כמו במבחן"])
            playwright.expect(page.locator(".mx-hq h2")).to_have_text("בחנים לקראת המבחן")
            playwright.expect(cards.nth(0)).to_contain_text("12 שאלות")
            playwright.expect(cards.nth(0).locator(".mx-hq-today")).to_have_text("מומלץ להיום")   # 7 to 4 days before
            playwright.expect(cards.nth(2).locator(".mx-hq-today")).to_have_count(0)
            assert not errors, errors
        finally:
            browser.close()
    exam_in(auth, 10)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            playwright.expect(page.locator(".mx-hq .mx-hq-card b")).to_have_text(["מבחן תרגול 1", "מבחן תרגול 2"])
            playwright.expect(page.locator(".mx-hq h2")).to_have_text("בחנים")
            assert not errors, errors
        finally:
            browser.close()


def test_three_days_before_the_second_and_the_exam_like_quiz_are_for_today(exam_server):
    url, auth = exam_server
    exam_in(auth, 3)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            today = page.locator(".mx-hq-card:has(.mx-hq-today) b")
            playwright.expect(today).to_have_text(["מבחן תרגול 2", "מבחן תרגול כמו במבחן"])
            playwright.expect(page.locator('[data-hq="s1"]')).to_be_enabled()   # still open
            assert not errors, errors
        finally:
            browser.close()


def test_a_strengthening_quiz_answers_right_away_and_offers_the_worked_example(exam_server):
    url, auth = exam_server
    key = exam_in(auth, 6)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            page.locator('[data-hq="s1"]').click()
            sheet = page.locator(".mx-quiz-sheet")
            playwright.expect(sheet.locator(".mx-uchip")).to_have_text("מבחן תרגול 1")
            sheet.locator(".mx-choices button:not([data-right])").first.click()
            fb = sheet.locator(".mx-quiz-fb")
            playwright.expect(fb.locator(".mx-bad")).to_contain_text("התשובה הנכונה מסומנת")
            playwright.expect(sheet.locator(".mx-choices button.right")).to_have_count(1)
            playwright.expect(sheet.locator(".mx-choices button.wrong")).to_have_count(1)
            fb.locator("summary", has_text="לראות דוגמה פתורה").click()
            playwright.expect(fb.locator(".mx-example")).to_contain_text("פתחו")
            playwright.expect(sheet.locator(".mx-choices button").first).to_be_disabled()   # the first pick is the answer
            assert sheet.locator("[data-quiz-sure]").count() == 0
            # the rest right, then hand in: kept with its kind, exam and questions, and counted for the chance
            sheet.locator("[data-act=quiz-next]").click()
            n = sheet.locator(".mx-quiz-dots button").count()
            for i in range(1, n):
                sheet.locator(".mx-choices button[data-right]").first.click()
                playwright.expect(sheet.locator(".mx-quiz-fb .mx-ok")).to_be_visible()
                sheet.locator("[data-act=quiz-submit]" if i == n - 1 else "[data-act=quiz-next]").click()
            playwright.expect(sheet.locator("#mxTitle")).to_have_text(f"{n - 1} מתוך {n} נכונות")
            playwright.expect(sheet.locator(".mx-quiz-best")).to_contain_text(f"הכי טוב: {n - 1}/{n}")
            last = stored(page)["quizzes"][-1]
            assert (last["kind"], last["exam"], len(last["qs"]), last["right"]) == ("s1", key, n, n - 1)
            assert n == 12 and not set(last["qs"]) - {f"{s}:{i}" for s in T + K for i in range(30)}
            assert stored(page)["tries"][last["qs"][0].split(":")[0]] >= 9
            assert not errors, errors
        finally:
            browser.close()


def test_a_retake_has_new_questions_and_the_card_shows_the_best_and_the_change(exam_server):
    url, auth = exam_server
    key = exam_in(auth, 6)
    at = lambda h: (datetime.now(timezone.utc) - timedelta(hours=h)).isoformat()
    tries = [{"at": at(5), "n": 12, "right": 7, "units": ["t", "k"], "weak": [], "kind": "s1", "exam": key, "qs": []},
             {"at": at(4), "n": 12, "right": 10, "units": ["t", "k"], "weak": [], "kind": "s1", "exam": key, "qs": []}]
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised(quizzes=tries))
            card = page.locator('[data-hq="s1"]')
            playwright.expect(card.locator(".mx-hq-best")).to_have_text("הכי טוב: 10/12 · +3 מהפעם הקודמת")
            card.click()
            answer_all(page)
            first = set(stored(page)["quizzes"][-1]["qs"])
            page.locator("[data-hq=s1]").last.click()   # the result's retake button
            answer_all(page, right=False)
            second = stored(page)["quizzes"][-1]
            assert not set(second["qs"]) & first                                   # new questions
            page.locator(".mx-quiz-sheet .mx-x").click()
            playwright.expect(page.locator('.mx-hq [data-hq="s1"] .mx-hq-best')).to_have_text("הכי טוב: 12/12 · -12 מהפעם הקודמת")
            assert not errors, errors
        finally:
            browser.close()


def test_the_exam_like_quiz_waits_for_the_end_and_lists_sure_but_wrong(exam_server):
    url, auth = exam_server
    exam_in(auth, 3)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            page.locator('[data-hq="exam"]').click()
            sheet = page.locator(".mx-quiz-sheet")
            sheet.locator(".mx-choices button:not([data-right])").first.click()
            playwright.expect(sheet.locator(".mx-quiz-fb")).to_be_empty()          # no feedback until the end
            playwright.expect(sheet.locator(".mx-choices button.wrong")).to_have_count(0)
            sheet.locator('[data-quiz-sure="2"]').click()
            playwright.expect(sheet.locator('[data-quiz-sure="2"]')).to_have_attribute("aria-pressed", "true")
            sheet.locator("[data-act=quiz-next]").click()
            n = sheet.locator(".mx-quiz-dots button").count()
            for i in range(1, n):
                sheet.locator(".mx-choices button:not([data-right])" if i == 1 else ".mx-choices button[data-right]").first.click()
                if i == 1:
                    sheet.locator('[data-quiz-sure="2"]').click()
                sheet.locator("[data-act=quiz-submit]" if i == n - 1 else "[data-act=quiz-next]").click()
            playwright.expect(sheet.locator("#mxTitle")).to_have_text(f"{n - 2} מתוך {n} נכונות")
            playwright.expect(sheet.locator(".mx-quiz-units-score > div")).to_have_count(2)   # per unit
            assert sheet.locator(".mx-quiz-plan li").count() <= 3
            playwright.expect(sheet.locator(".mx-quiz-surewrong li")).to_have_count(2)
            playwright.expect(sheet.locator(".mx-quiz-surewrong h4")).to_have_text("הייתי בטוח/ה וטעיתי")
            note = sheet.locator("[data-quiz-note]")
            note.locator("input").fill("לקרוא כל שאלה פעמיים")
            note.locator("button").click()
            playwright.expect(note.locator("[role=status]")).to_have_text("נשמר.")
            last = stored(page)["quizzes"][-1]
            assert last["kind"] == "exam" and last["note"] == "לקרוא כל שאלה פעמיים" and last["sure"].count(2) == 2
            units = {q.split(":")[0].split("_")[0] for q in last["qs"]}
            assert units == {"t", "k"}                                              # the exam's units only, mixed
            assert not errors, errors
        finally:
            browser.close()


def test_the_exam_like_quiz_is_handed_in_without_confidence_or_reflection(exam_server):
    url, auth = exam_server
    exam_in(auth, 3)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            page.locator('[data-hq="exam"]').click()
            n = answer_all(page)
            playwright.expect(page.locator(".mx-quiz-sheet #mxTitle")).to_have_text(f"{n} מתוך {n} נכונות")
            playwright.expect(page.locator(".mx-quiz-surewrong")).to_have_count(0)
            last = stored(page)["quizzes"][-1]
            assert "note" not in last and set(last["sure"]) == {None}
            assert not errors, errors
        finally:
            browser.close()


def test_too_little_practice_lists_the_topics_to_learn_and_never_quizzes_unstarted_ones(exam_server):
    url, auth = exam_server
    exam_in(auth, 6)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised(skills=[]))   # nothing practised yet: no question to draw
            blocked = page.locator('.mx-hq-card.blocked[data-hq-kind="s1"]')
            playwright.expect(blocked).to_be_visible()
            playwright.expect(page.locator("[data-hq]")).to_have_count(0)   # none can start
            playwright.expect(blocked).to_contain_text("אפשר להתחיל אחרי שתתרגלו קודם")
            blocked.locator('[data-id="t_simplify"]').click()
            playwright.expect(page.locator(".mx-sheet")).to_be_visible()
            assert not errors, errors
        finally:
            browser.close()
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised(skills=T))   # unit k never practised
            page.locator('[data-hq="s1"]').click()
            answer_all(page)
            assert not [q for q in stored(page)["quizzes"][-1]["qs"] if q.startswith("k_")]
            assert not errors, errors
        finally:
            browser.close()


def test_no_weakness_words_on_the_quiz_cards_and_results(exam_server):
    url, auth = exam_server
    exam_in(auth, 3)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, practised())
            words = page.locator(".mx-hq").inner_text()
            page.locator('[data-hq="exam"]').click()
            answer_all(page, right=False)
            words += page.locator(".mx-quiz-sheet").inner_text()
            assert "חולשה" not in words and "חלש" not in words
            assert "לחזק" in words
            assert not errors, errors
        finally:
            browser.close()


def test_a_week_before_the_november_exam_end_to_end(exam_server):
    """Home → the exam and three quizzes → quiz 1 with feedback → a retake with new questions → the quiz like the exam
    with confidence marks → the plan shows the quiz steps done → the path tab still has review and the trail."""
    url, auth = exam_server
    key = exam_in(auth, 6, units=("t", "t2", "k", "l", "o"))
    skills = T + ["t_gcf", "t_trinomial", "t_factor_formula", "t_quad_eq"] + K + ["l_30_side", "l_30_converse", "o_median"]
    progress = practised(skills)
    old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    progress["done"]["k_def"] = progress["seen"]["k_def"] = old
    progress["review"] = {"k_def": {"box": 0, "due": "2020-01-01"}}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page, errors = open_app(browser, url, progress)
            exam = page.locator(".mx-home-exam")
            playwright.expect(exam).to_contain_text("עוד 6 ימים")
            playwright.expect(page.locator(".mx-hq .mx-hq-card")).to_have_count(3)
            exam.click()   # the plan opens now: what is done after this counts for its steps
            page.locator(".mx-prep-sheet .mx-x").click()
            page.wait_for_timeout(50)
            # quiz 1: feedback after a wrong answer, then all right
            page.locator('.mx-hq [data-hq="s1"]').click()
            sheet = page.locator(".mx-quiz-sheet")
            sheet.locator(".mx-choices button:not([data-right])").first.click()
            playwright.expect(sheet.locator(".mx-quiz-fb .mx-bad")).to_be_visible()
            sheet.locator("[data-act=quiz-next]").click()
            n = sheet.locator(".mx-quiz-dots button").count()
            for i in range(1, n):
                sheet.locator(".mx-choices button[data-right]").first.click()
                sheet.locator("[data-act=quiz-submit]" if i == n - 1 else "[data-act=quiz-next]").click()
            first = set(stored(page)["quizzes"][-1]["qs"])
            # a retake: new questions
            sheet.locator("[data-hq=s1]").click()
            answer_all(page)
            assert not set(stored(page)["quizzes"][-1]["qs"]) & first
            sheet.locator(".mx-x").click()
            # the quiz like the exam, with confidence marks
            page.locator('.mx-hq [data-hq="exam"]').click()
            answer_all(page, sure=2)
            last = stored(page)["quizzes"][-1]
            assert last["kind"] == "exam" and last["exam"] == key and last["sure"] == [2] * len(last["qs"])
            assert {q.split(":")[0] for q in last["qs"]} <= set(skills)
            sheet.locator(".mx-x").click()
            # the plan: quiz 1 and the exam-like quiz done, quiz 2 not yet
            page.locator(".mx-home-exam").click()
            done = page.locator(".mx-prep-sheet .mx-prep-step.done")
            playwright.expect(done.filter(has_text="מבחן תרגול 1")).to_have_count(1)
            playwright.expect(done.filter(has_text="מבחן תרגול כמו במבחן")).to_have_count(1)
            playwright.expect(done.filter(has_text="מבחן תרגול 2")).to_have_count(0)
            page.locator(".mx-prep-sheet .mx-x").click()
            # the path tab: review and the trail
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator(".mx-review")).to_be_visible()
            playwright.expect(page.locator(".mx-trail")).to_be_visible()
            assert not errors, errors
        finally:
            browser.close()
