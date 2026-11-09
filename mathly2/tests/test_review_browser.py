"""The חזרה tab in a real browser (add-review-tab 3.1)."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_path_browser import KID, KID_ID, bank, browser, path_page, world  # noqa: F401
from mathly2.tests.test_quizzes_api import right_index


def open_review(browser, url, width=360):
    page = offline_formulas(browser.new_page(viewport={"width": width, "height": 800}))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.fill("#email", KID)
    page.click("#dev button")
    page.click(".subject-card")
    page.click(".tabs a[href='#/review']")
    page.wait_for_selector("#review")
    page.errors = errors
    return page


def seed(store, bank, lessons, n=3):
    skill = next(s["id"] for s in bank.skills if s["unit"] in lessons and len(bank.question_keys(s["id"])) >= n)
    keys = bank.question_keys(skill)[:n]
    from datetime import datetime, timedelta, timezone
    store.add_review(KID_ID, [(skill, k, "quiz") for k in keys], datetime(2026, 11, 1, tzinfo=timezone.utc))
    for i, k in enumerate(keys):                                                   # a clear order: the first is the oldest
        store._review[(KID_ID, k)]["wrong_at"] = datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(minutes=i)
    return skill, keys


def click_choice(page, bank, skill, key, right):
    index = right_index(bank, skill, key, right)
    page.click(f"#review-choices .ex-choice[data-i='{index}']")


@pytest.mark.parametrize("width", [320, 360, 1280])
def test_the_tab_bar_with_six_tabs_fits_and_the_empty_state_says_so(browser, bank, width):
    app, store = world(bank, [next(iter({s["unit"] for s in bank.skills}))])
    with running(app) as url:
        page = open_review(browser, url, width)
        assert page.locator(".tabs a").count() == 6 and page.get_attribute(".tabs a[aria-current=page]", "href") == "#/review"
        assert page.locator("#review-empty").count() == 1 and "אין שאלות שמחכות" in page.inner_text("#review-count")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        boxes = page.eval_on_selector_all(".tabs a", "els => els.map(e => { const r = e.getBoundingClientRect(); return [r.left, r.right, e.scrollWidth > e.clientWidth]; })")
        assert all(left >= 0 and right <= width and not clipped for left, right, clipped in boxes)         # every label is whole and on screen
        assert not page.errors


def test_a_wrong_answer_keeps_the_question_with_the_mistake_and_never_marks_the_right_choice_and_a_right_one_removes_it(browser, bank):
    lessons = [next(s["unit"] for s in bank.skills if len(bank.question_keys(s["id"])) >= 3)]
    app, store = world(bank, lessons)
    skill, keys = seed(store, bank, lessons)
    with running(app) as url:
        page = open_review(browser, url)
        assert "3 שאלות מחכות" in page.inner_text("#review-count") and page.get_attribute("#review-q", "data-key") == keys[0]          # the oldest first
        click_choice(page, bank, skill, keys[0], right=False)
        page.wait_for_selector("[data-result=wrong]")
        assert "3 שאלות מחכות" in page.inner_text("#review-count") and page.locator("#review-mistake").count() == 1
        assert page.locator(".ex-choice.right").count() == 0 and page.locator(".ex-choice.wrong").count() == 1                      # the right choice is not shown
        page.click("#review-next")
        assert page.get_attribute("#review-q", "data-key") == keys[1]                                                                 # not the one just answered
        click_choice(page, bank, skill, keys[1], right=True)
        page.wait_for_selector("[data-result=right]")
        assert "2 שאלות מחכות" in page.inner_text("#review-count") and [r["question_key"] for r in store.review_of(KID_ID)] == [keys[0], keys[2]]
        page.click("#review-next")
        click_choice(page, bank, skill, keys[0], right=True)                                                                          # the oldest wrong one, now right
        page.click("#review-next")
        click_choice(page, bank, skill, keys[2], right=True)
        page.wait_for_selector("[data-result=right]")
        assert "אין שאלות שמחכות" in page.inner_text("#review-count") and store.review_of(KID_ID) == []
        assert not page.errors
