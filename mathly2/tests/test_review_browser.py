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


def seed(store, bank, lessons, per=(2, 1)):
    """Review items on two skills of the lessons: per[0] on the first, per[1] on the second. The skill that comes later in the bank has the oldest mistake."""
    from datetime import datetime, timedelta, timezone
    skills = [s["id"] for s in bank.skills if s["unit"] in lessons and len(bank.question_keys(s["id"])) >= 3][:2]
    t0 = datetime(2026, 11, 1, tzinfo=timezone.utc)
    keys = {skills[0]: bank.question_keys(skills[0])[:per[0]], skills[1]: bank.question_keys(skills[1])[:per[1]]}
    store.add_review(KID_ID, [(skills[1], keys[skills[1]][0], "quiz")], t0)
    for i, k in enumerate(keys[skills[0]]):
        store.add_review(KID_ID, [(skills[0], k, "practice")], t0 + timedelta(minutes=i + 1))
    for i, k in enumerate(keys[skills[1]][1:]):
        store.add_review(KID_ID, [(skills[1], k, "quiz")], t0 + timedelta(minutes=10 + i))
    return skills, keys


def click_choice(page, bank, skill, key, right):
    index = right_index(bank, skill, key, right)
    page.click(f".review-card[data-key='{key}'] .ex-choice[data-i='{index}']")


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


def test_every_question_is_a_card_grouped_by_skill_and_a_wrong_answer_keeps_it_with_the_mistake_and_a_retry(browser, bank):
    lessons = list({s["unit"] for s in bank.skills if len(bank.question_keys(s["id"])) >= 3})[:3]
    app, store = world(bank, lessons)
    skills, keys = seed(store, bank, lessons)
    with running(app) as url:
        page = open_review(browser, url)
        assert "3 שאלות מחכות" in page.inner_text("#review-count")
        assert [page.get_attribute(f".review-group >> nth={i}", "data-skill") for i in range(2)] == skills               # a heading per skill, the bank's order
        assert page.locator(".review-card").count() == 3 and page.locator(f".review-group[data-skill='{skills[0]}'] .review-card").count() == 2
        assert "2 כרטיסים" in page.inner_text(f".review-group[data-skill='{skills[0]}'] h3") and "כרטיס אחד" in page.inner_text(f".review-group[data-skill='{skills[1]}'] h3")
        assert page.locator(f".review-group[data-skill='{skills[0]}'] .review-card >> nth=0").get_attribute("data-key") == keys[skills[0]][0]     # oldest first
        wrong = keys[skills[0]][0]
        click_choice(page, bank, skills[0], wrong, right=False)
        page.wait_for_selector(f".review-card[data-key='{wrong}'] [data-result=wrong]")
        card = page.locator(f".review-card[data-key='{wrong}']")
        assert card.locator(".review-mistake").count() == 1 and card.locator(".ex-choice.right").count() == 0 and page.locator(".ex-choice.right").count() == 0
        assert "3 שאלות מחכות" in page.inner_text("#review-count") and card.locator(".ex-choice:not([disabled])").count() == 0
        card.locator("[data-again]").click()
        assert card.locator(".ex-choice:not([disabled])").count() == card.locator(".ex-choice").count() > 0 and card.locator(".review-mistake").count() == 0     # tried again
        assert not page.errors


def test_a_right_answer_marks_the_card_done_lowers_both_counts_and_the_last_card_of_a_skill_removes_its_heading(browser, bank):
    lessons = list({s["unit"] for s in bank.skills if len(bank.question_keys(s["id"])) >= 3})[:3]
    app, store = world(bank, lessons)
    skills, keys = seed(store, bank, lessons)
    with running(app) as url:
        page = open_review(browser, url)
        click_choice(page, bank, skills[1], keys[skills[1]][0], right=True)                                                        # the second skill's only card
        page.wait_for_selector(f".review-card[data-key='{keys[skills[1]][0]}'].done")
        assert "2 שאלות מחכות" in page.inner_text("#review-count") and page.locator(f".review-group[data-skill='{skills[1]}'] h3").is_hidden()
        assert page.locator(f".review-group[data-skill='{skills[0]}'] h3").is_visible()
        click_choice(page, bank, skills[0], keys[skills[0]][0], right=True)
        page.wait_for_selector(f".review-card[data-key='{keys[skills[0]][0]}'].done")
        assert "1" in page.inner_text(f".review-group[data-skill='{skills[0]}'] .review-skill-count") or "כרטיס אחד" in page.inner_text(f".review-group[data-skill='{skills[0]}'] .review-skill-count")
        click_choice(page, bank, skills[0], keys[skills[0]][1], right=True)
        page.wait_for_selector("#review-empty")
        assert "אין שאלות שמחכות" in page.inner_text("#review-count") and store.review_of(KID_ID) == []
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert not page.errors
