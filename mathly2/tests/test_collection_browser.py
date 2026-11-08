"""The collection screen in a real browser: what a student has mastered, and the empty start."""
import uuid

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running

KID = "kid@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))


@pytest.fixture
def world():
    bank = load_bank()
    store = InMemoryStore()
    store.add_member(store.create_class("setup", "A", lessons=[u["id"] for u in bank.lessons])["id"], KID)
    return create_app(Settings(), bank=bank, store=store), store, bank


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def collection_page(browser, url):
    page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
    page.goto(url + "#/collection")
    page.fill("#email", KID)
    page.click("#dev button")
    page.wait_for_selector("#collection")
    return page


def test_a_skill_mastered_through_the_server_appears_in_the_collection(browser, world):
    app, store, bank = world
    skill = bank.skills[0]
    store.save_progress(KID_ID, skill["id"], started_at="then", mastered_at="then")
    with running(app) as url:
        page = collection_page(browser, url)
        assert skill["name"] in page.inner_text("#done-skills") and "מיומנויות שנשלטו (1)" in page.inner_text("#collection")
        assert "קבוצות כוכבים (0)" in page.inner_text("#collection")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.click("a[href='#/subject/math/path']")
        page.wait_for_selector(".trail")


def test_the_collection_starts_empty_with_a_hint(browser, world):
    app, _, _ = world
    with running(app) as url:
        page = collection_page(browser, url)
        assert "מיומנויות שנשלטו (0)" in page.inner_text("#collection") and page.locator("#done-skills").count() == 0


# --- add-rewards 4.2 / 5.1: constellations and comets ---

PHONE = {"width": 360, "height": 800}


def master_lesson(store, bank, lesson_id):
    ids = [s["id"] for s in bank.skills if s["unit"] == lesson_id]
    for skill in ids:
        store.save_progress(KID_ID, skill, started_at="then", mastered_at="then")
    return ids


def lessons_of_size(bank, *sizes):
    from collections import Counter
    counts = Counter(s["unit"] for s in bank.skills)
    return [next(l for l, n in counts.items() if n == size) for size in sizes]


def test_constellations_of_2_4_and_6_stars_and_the_fallback_fit_a_360px_screen(browser, world):
    app, _, _ = world
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url)
        page.evaluate("""async () => {
          const { constellationSvg } = await import('/static/sky.js');
          const host = document.createElement('div'); host.id = 'probe'; host.style.cssText = 'display:grid;grid-template-columns:repeat(2,130px);gap:8px;padding:8px';
          host.innerHTML = [['t', 2], ['k', 4], ['h', 6], ['zz', 4], ['zz', 7]].map(([id, n]) => constellationSvg(id, 'בדיקה', n)).join('');
          document.body.append(host);
          const style = document.createElement('style'); style.textContent = '.con{width:100%;max-width:130px;height:110px;overflow:visible}'; document.head.append(style);
        }""")
        svgs = page.locator("#probe svg.con")
        assert svgs.count() == 5
        for i, stars in enumerate([2, 4, 6, 4, 7]):
            svg = svgs.nth(i)
            assert svg.locator("path").count() == stars                                  # one star per skill, fallback included
            box = svg.bounding_box()
            assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
            assert "בדיקה" in svg.get_attribute("aria-label") and str(stars) in svg.get_attribute("aria-label")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_mastering_a_lessons_last_skill_adds_its_constellation(browser, world):
    app, store, bank = world
    two, three = lessons_of_size(bank, 2, 3)
    ids = [s["id"] for s in bank.skills if s["unit"] == two]
    store.save_progress(KID_ID, ids[0], started_at="then", mastered_at="then")
    with running(app) as url:
        page = collection_page(browser, url)
        assert "קבוצות כוכבים (0)" in page.inner_text("#collection")
        store.save_progress(KID_ID, ids[1], started_at="then", mastered_at="then")   # the lesson's last skill
        page.reload(); page.wait_for_selector("#collection")
        assert "קבוצות כוכבים (1)" in page.inner_text("#collection")
        card = page.locator(f"#done-lessons .con-card[data-lesson='{two}']")
        assert card.count() == 1 and card.locator("svg.con path").count() == 2


def test_the_collection_shows_caught_comets_and_question_marks_for_the_rest(browser, world):
    app, store, _ = world
    for c in ("pi", "e", "zero"):
        store.add_comet(KID_ID, c)
    with running(app) as url:
        page = collection_page(browser, url)
        tiles = page.locator("#comets .comet-tile")
        assert tiles.count() == 12 and page.locator("#comets .comet-tile.have").count() == 3
        assert page.locator("#comets .comet-tile:not(.have)").count() == 9
        assert "π" in page.inner_text("#comets .comet-tile.have >> nth=0") and "פאי" in page.inner_text("#comets")
        assert page.locator("#comets .comet-tile:not(.have)", has_text="עוד לא נתפס").count() == 9
        assert "3 מתוך 12" in page.inner_text("#collection")
        page.click("#comets [data-comet='pi']")                                           # a caught comet opens its fact
        assert "היחס בין ההיקף" in page.inner_text(".comet-dialog")
        page.keyboard.press("Escape")
        assert page.locator(".comet-dialog").count() == 0
        page.click("#comets .comet-tile:not(.have) >> nth=0")                              # a missing one opens a hint, no fact
        assert "עוד לא נתפס" in page.inner_text(".comet-dialog") and "היחס בין" not in page.inner_text(".comet-dialog")
        page.click(".comet-dialog button")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_the_collection_dims_a_faded_skill_and_says_so(browser, world):
    from datetime import timedelta
    from mathly2 import clock
    app, store, bank = world
    skill = bank.skills[0]["id"]
    store.save_progress(KID_ID, skill, started_at="then", mastered_at="then")
    store.add_answer(KID_ID, skill, "k", True, True, None, clock.school_day() - timedelta(days=30))
    with running(app) as url:
        page = collection_page(browser, url)
        assert "דועך" in page.inner_text("#done-skills li.faded")
