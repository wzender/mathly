"""Comets on the exercise screen, in a real browser (add-rewards 4.1) and the whole reward loop (6.1)."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_exercise_browser import KID, KID_ID, PHONE, browser, choose, key_on_screen, raw, world  # noqa: F401


def four_right_today(store, skill):
    for i in range(4):
        store.add_answer(KID_ID, skill, f"seed{i}", True, True, None, clock.school_day())


def sign_in_at(browser, url, skill, **options):
    page = offline_formulas(browser.new_page(viewport=PHONE, **options))
    page.goto(f"{url}#/skill/{skill}")
    page.fill("#email", KID)
    page.click("#dev button")
    page.wait_for_selector(".mx-sheet #ex-q")
    return page


def test_the_fifth_right_answer_brings_a_comet_that_can_be_caught_while_answering_stays_possible(browser, world):
    app, store, bank, ids = world
    skill = ids["bare"]
    four_right_today(store, skill)
    app.state.comet_roll = lambda: 0.0
    with running(app) as url:
        page = sign_in_at(browser, url, skill)
        choose(page, bank, skill)
        page.wait_for_selector("#ex-fb .ex-ok")
        page.wait_for_selector("#comet")                                           # it crosses
        assert page.evaluate("document.getAnimations().some(a => a.animationName === 'comet-fly')")
        page.click("#ex-skip")                                                    # answering stays possible while it flies
        page.wait_for_selector("#ex-choices .ex-choice")
        page.evaluate("document.getElementById('comet').click()")                 # a tap catches it (a script click: the target moves)
        page.wait_for_selector(".comet-dialog")
        text = page.inner_text(".comet-dialog")
        assert "תפסתם שביט נדיר" in text and len(text) > 60
        page.click(".comet-dialog button")
        assert [c for c in store.comets_of(KID_ID)] and len(store.comets_of(KID_ID)) == 1
        choose(page, bank, skill)                                                 # a sixth right answer the same day
        page.wait_for_selector("#ex-fb .ex-ok")
        assert page.locator("#comet").count() == 0                               # no second comet today


def test_under_reduced_motion_a_still_comet_button_appears_once_and_nothing_flies(browser, world):
    app, store, bank, ids = world
    skill = ids["bare"]
    four_right_today(store, skill)
    app.state.comet_roll = lambda: 0.0
    with running(app) as url:
        page = sign_in_at(browser, url, skill, reduced_motion="reduce")
        choose(page, bank, skill)
        page.wait_for_selector("#ex-fb #comet.still")
        assert page.locator("#comet svg").count() == 0                            # no moving drawing
        assert page.evaluate("document.getAnimations().filter(a => a.animationName === 'comet-fly').length") == 0
        assert "שביט" in page.inner_text("#comet")
        page.click("#comet")
        page.wait_for_selector(".comet-dialog")
        page.keyboard.press("Escape")
        assert len(store.comets_of(KID_ID)) == 1 and page.locator("#comet").count() == 0


# --- 6.1 the whole reward loop ---

def test_the_reward_loop_goal_comet_collection_and_constellation(browser):
    from datetime import timedelta
    from collections import Counter
    from mathly2.bank import load_bank
    from mathly2.config import Settings
    from mathly2.main import create_app
    from mathly2.store import InMemoryStore
    from mathly2.tests.test_exercise_browser import question_key

    bank = load_bank()
    sizes = Counter(s["unit"] for s in bank.skills)
    lesson = next(l for l, n in sizes.items() if n == 2 and all(len(s.get("questions", [])) >= 4 for s in bank.skills if s["unit"] == l))
    first, last = [s["id"] for s in bank.skills if s["unit"] == lesson]
    store = InMemoryStore()
    store.add_member(store.create_class("setup", "A", lessons=[lesson])["id"], KID)
    store.save_progress(KID_ID, first, started_at="then", mastered_at="then")                  # the lesson's first skill is done
    yesterday = clock.school_day() - timedelta(days=1)
    keys = bank.question_keys(last)
    for key in keys[:2]:                                                                        # two right answers yesterday on the last skill
        store.add_answer(KID_ID, last, key, True, True, None, yesterday)
    app = create_app(Settings(), bank=bank, store=store)
    app.state.comet_roll = lambda: 0.0
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url)
        page.fill("#email", KID)
        page.click("#dev button")
        page.click(".subject-card")
        page.click(".tabs a[href='#/subject/math/path']")
        page.wait_for_selector(".orbit")
        assert "קבוצות" not in page.inner_text("#lesson-" + lesson)
        page.click(f".star[data-skill='{last}']")
        page.wait_for_selector("#ex-q")
        for n in range(1, 6):                                                                   # five right answers today
            key = key_on_screen(page)
            question = next(q for q in bank.skill(last)["questions"] if question_key(last, q) == key)
            page.click(f"#ex-choices .ex-choice[data-i='{next(i for i, c in enumerate(question['choices']) if c.get('correct'))}']")
            page.wait_for_selector("#ex-fb .ex-ok")
            if n == 1:
                assert page.locator("#ex-mastered").count() == 1                                # the third right answer on a second day masters it
            if n < 5:
                assert page.locator("#comet").count() == 0
                page.click("#ex-skip")
                page.wait_for_function("(k) => document.querySelector('#ex-q')?.dataset.key !== k", arg=key)
        page.wait_for_selector("#comet")                                                        # the fifth brings the first comet
        page.evaluate("document.getElementById('comet').click()")
        page.wait_for_selector(".comet-dialog")
        name = page.inner_text(".comet-dialog .comet-card b")
        page.click(".comet-dialog button")
        page.click(".mx-x")                                                                     # back to the path: the goal is reached
        page.wait_for_function("document.querySelector('#goal-text')?.innerText.includes('5 מתוך 5')")   # the path is fetched again
        assert "✓" in page.inner_text("#goal-text")
        page.click("a[href='#/collection']")                                                    # the collection has the comet and the constellation
        page.wait_for_selector("#comets")
        assert name in page.inner_text("#comets .comet-tile.have") and "1 מתוך 12" in page.inner_text("#collection")
        assert page.locator(f"#done-lessons .con-card[data-lesson='{lesson}']").count() == 1
