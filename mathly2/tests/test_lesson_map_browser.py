"""The home's lessons map and a lesson round in a real browser (game-home-lesson-rounds 2.1-2.3)."""
import os
from datetime import timedelta

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, only, running
from mathly2.tests.test_home_browser import KID, KID_ID, PHONE, TEACHER, no_sideways_scroll, sign_in, to_home

SHOTS = os.environ.get("MATHLY_SHOTS")          # a folder: save screenshots there to look at the screens
STAMP = "2026-10-05T10:00:00+00:00"


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def world(bank, n=4):
    lessons = [l["id"] for l in bank.lessons if any(s["unit"] == l["id"] and bank.question_keys(s["id"]) for s in bank.skills)][:n]
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=lessons, teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    small = only(bank, lessons)
    return create_app(Settings(), bank=small, store=store), store, small, lessons


def shot(page, name):
    if SHOTS:
        page.screenshot(path=os.path.join(SHOTS, f"{name}.png"), full_page=True)


def right_index(bank, key):
    skill = next(s for s in bank.skills if key in bank.question_keys(s["id"]))
    from mathly2.bank import question_key
    question = next(q for q in skill["questions"] if question_key(skill["id"], q) == key)
    return next(i for i, c in enumerate(question["choices"]) if c.get("correct"))


def test_home_is_a_map_of_the_lessons_with_stars_and_a_play_button(browser, bank):
    app, store, small, lessons = world(bank)
    first = [s["id"] for s in small.skills if s["unit"] == lessons[0]]
    for s in first:
        store.save_progress(KID_ID, s, started_at=STAMP, mastered_at=STAMP)                    # lesson 1 perfect
    store.set_lesson_dates({lessons[2]: clock.school_day() - timedelta(days=3)})               # lesson 3 behind
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#lesson-map")
        nodes = page.locator(".lnode")
        assert nodes.count() == len(lessons)
        assert nodes.nth(0).get_attribute("data-stars") == "3" and "👑" in nodes.nth(0).inner_text()
        assert "⏰" in nodes.nth(2).inner_text()
        assert page.locator("#stars-count").inner_text() == f"⭐ 3 מתוך {3 * len(lessons)}"
        assert page.locator("#play").get_attribute("href") == f"#/round/{lessons[2]}"            # the behind lesson comes first
        assert page.locator(".lnode.next").get_attribute("data-lesson") == lessons[2]
        assert page.locator(".tabs a").nth(1).inner_text() == "העמקה" and page.locator("#behind-card").count() == 0
        no_sideways_scroll(page)
        shot(page, "home")
        assert page.errors == []


def test_a_round_from_the_map_gives_feedback_and_ends_with_stars(browser, bank):
    app, store, small, lessons = world(bank, 2)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.click("#play")
        page.wait_for_selector(".round-layer #ex-q")
        total = int(page.locator("#rd-count").inner_text().split()[-1])
        shot(page, "round-question")
        for i in range(total):
            key = page.locator("#ex-q").get_attribute("data-key")
            pick = right_index(small, key) if i < total - 1 else None
            if pick is None:                                                   # the last one wrong
                page.locator(f".ex-choice:not([data-i='{right_index(small, key)}'])").first.click()
                page.wait_for_selector(".ex-bad")
                shot(page, "round-wrong")
            else:
                page.click(f".ex-choice[data-i='{pick}']")
                page.wait_for_selector(".ex-ok")
            page.click("#rd-next")
            if i < total - 1:
                page.wait_for_function(f"document.querySelector('#rd-count').textContent.includes('{i + 2} מתוך')")
        page.wait_for_selector("#rd-result")
        assert page.locator("#rd-score").inner_text().replace("\n", " ").startswith(f"{total - 1}")
        assert page.locator(".rd-bigstars span.on").count() == 2                     # 9 of 10: two stars
        shot(page, "round-result")
        page.click("#rd-result [data-close]")
        page.wait_for_selector(f".lnode[data-lesson='{lessons[0]}'][data-stars='2']")                # the map refreshes with the new stars
        assert page.evaluate("location.hash") == "#/subject/math"
        assert page.errors == []


def test_a_link_to_a_round_opens_the_home_under_it(browser, bank):
    app, _, _, lessons = world(bank, 2)
    with running(app) as url:
        page = sign_in(browser, url, f"#/round/{lessons[1]}")
        page.wait_for_selector(".round-layer #ex-q")
        assert page.locator("#lesson-map").count() == 1
        page.click(".mx-x")
        page.wait_for_function("!document.querySelector('.round-layer')")
        assert page.errors == []
