"""One skill from the path to mastery in a real browser, with the server's clock moved to the next day."""
import uuid
from datetime import datetime, timezone

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.bank import load_bank, question_key
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running

KID = "kid@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))
MONDAY = datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc)
TUESDAY = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
SKILL = "t_ext"


def test_two_right_answers_then_a_third_the_next_day_master_the_skill_and_the_owl_moves_on(monkeypatch):
    moment = {"now": MONDAY}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    bank = load_bank()
    store = InMemoryStore()
    store.add_member(store.create_class("setup", "A", lessons=[u["id"] for u in bank.lessons])["id"], KID)
    app = create_app(Settings(), bank=bank, store=store)

    def answer_right(page):
        key = page.get_attribute("#ex-q", "data-key")
        question = next(q for q in bank.skill(SKILL)["questions"] if question_key(SKILL, q) == key)
        page.click(f"#ex-choices .ex-choice[data-i='{next(i for i, c in enumerate(question['choices']) if c.get('correct'))}']")
        page.wait_for_selector("#ex-fb .ex-ok")

    with running(app) as url, playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        page.goto(url)
        page.fill("#email", KID)
        page.click("#dev button")
        page.click(".subject-card")
        page.click(".tabs a[href='#/subject/math/path']")

        # the path: nothing started, the owl on the first skill; open the skill from its star
        page.wait_for_selector(".star")
        assert "לא התחלת" in page.inner_text(f".star[data-skill='{SKILL}'] .lbl")
        assert page.get_attribute(".star.next", "data-skill") == SKILL                  # t_ext is the first skill of the first lesson
        page.click(f".star[data-skill='{SKILL}']")
        page.wait_for_selector("#ex-q")

        # Monday: two right answers, first try, no help
        answer_right(page)
        assert "1 תשובה נכונה ברצף" in page.inner_text("#ex-fb")
        page.click("#ex-skip")
        page.wait_for_selector("#ex-q")
        answer_right(page)
        assert "2 תשובות נכונות ברצף" in page.inner_text("#ex-fb") and page.locator("#ex-mastered").count() == 0   # one day: not yet
        page.click("#ex-skip")
        page.wait_for_selector("#ex-q")

        # Tuesday on the server: the third right answer completes the rule
        moment["now"] = TUESDAY
        answer_right(page)
        page.wait_for_selector("#ex-mastered")
        assert "3 תשובות נכונות ברצף" in page.inner_text("#ex-fb") and page.locator(".ex-done").count() == 1

        # back on the path: the star is mastered, the owl has moved on, and the collection shows it
        page.click(".mx-x")
        page.wait_for_selector(".mx-layer", state="detached")
        page.wait_for_function("(id) => document.querySelector(`.star[data-skill='${id}'] .lbl`).innerText.includes('נשלטה')", arg=SKILL)   # the path refreshes
        assert page.locator(f".star[data-skill='{SKILL}'].next").count() == 0
        assert page.locator(".star.next").count() == 1 and page.get_attribute(".star.next", "data-skill") != SKILL
        page.click(".tabs a[href='#/collection']")
        page.wait_for_selector("#done-skills")
        assert bank.skill(SKILL)["name"] in page.inner_text("#done-skills")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        browser.close()

    assert store.get_progress(KID_ID, SKILL)["mastered_at"] == TUESDAY.isoformat()
