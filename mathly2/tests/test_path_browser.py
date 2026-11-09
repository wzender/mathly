"""The path in a real browser at phone width: orbits of every size, the states in words, the owl, keyboard use, reduced motion."""
import uuid
from collections import Counter

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, only, running

KID = "kid@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))
NOW = "2026-11-02T10:00:00+00:00"
PHONE = {"width": 360, "height": 800}
WORDS = {"not_started": "לא התחלת", "learning": "בלמידה", "mastered": "נשלטה"}


def lessons_by_size(bank):
    sizes = Counter(s["unit"] for s in bank.skills)
    pick = lambda n: next(lesson for lesson, count in sizes.items() if count == n)
    return pick(2), pick(3), pick(6)


@pytest.fixture(scope="module")
def bank():
    return load_bank()


def world(bank, lessons):
    store = InMemoryStore()
    store.add_member(store.create_class("setup", "A", lessons=list(lessons))["id"], KID)
    return create_app(Settings(), bank=only(bank, lessons), store=store), store


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def path_page(browser, url, scheme="light", **options):
    page = offline_formulas(browser.new_page(viewport=PHONE, color_scheme=scheme, **options))
    page.goto(url)
    page.fill("#email", KID)
    page.click("#dev button")
    page.click(".subject-card")
    page.click(".tabs a[href='#/subject/math/path']")
    page.wait_for_selector(".orbit")
    return page


# --- 4.1 the rings ---

def test_rings_of_2_3_and_6_skills_fit_a_360px_screen_and_keep_clear_of_the_hub(browser, bank):
    two, three, six = lessons_by_size(bank)
    app, _ = world(bank, [two, three, six])
    with running(app) as url:
        page = path_page(browser, url)
        assert page.locator(".orbit").count() == 3
        for lesson, n in ((two, 2), (three, 3), (six, 6)):
            orbit = page.locator(f"#lesson-{lesson}")
            hub = orbit.locator(".hub").bounding_box()
            stars = orbit.locator(".star .node")
            assert stars.count() == n
            for i in range(n):
                node = stars.nth(i).bounding_box()
                assert node["x"] >= 0 and node["x"] + node["width"] <= PHONE["width"], f"star {i + 1} of {lesson} leaves the screen"
                apart = (node["x"] + node["width"] <= hub["x"] or hub["x"] + hub["width"] <= node["x"]
                         or node["y"] + node["height"] <= hub["y"] or hub["y"] + hub["height"] <= node["y"])
                assert apart, f"star {i + 1} of {lesson} is over the hub"
            labels = orbit.locator(".star .lbl")
            for i in range(n):
                box = labels.nth(i).bounding_box()
                assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
            assert orbit.locator(".ring path").count() == (n - 1) + (1 if n > 2 else 0)        # the arcs between neighbours, and the faint closing one
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_stars_are_numbered_clockwise_from_the_top(browser, bank):
    _, _, six = lessons_by_size(bank)
    app, _ = world(bank, [six])
    with running(app) as url:
        page = path_page(browser, url)
        hub = page.locator(".hub").bounding_box()
        centre = (hub["x"] + hub["width"] / 2, hub["y"] + hub["height"] / 2)
        found = []
        for i in range(6):
            node = page.locator(".star .node").nth(i).bounding_box()
            found.append((node["x"] + node["width"] / 2 - centre[0], node["y"] + node["height"] / 2 - centre[1]))
        assert found[0][1] < 0 and abs(found[0][0]) < 5                       # 1 is at the top
        assert found[1][0] > 0 and found[2][0] > 0 and found[3][1] > 0        # then right, down, and round to the left
        assert found[4][0] < 0 and found[5][0] < 0


# --- 4.2 the states, the owl, the lessons shown ---

@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_each_state_says_its_word_the_mastered_star_differs_and_the_owl_is_on_the_next_one(browser, bank, scheme):
    two, three, _ = lessons_by_size(bank)
    app, store = world(bank, [two, three])
    first, second = (s["id"] for s in bank.skills if s["unit"] == two)
    store.save_progress(KID_ID, first, started_at=NOW, mastered_at=NOW)            # mastered
    store.save_progress(KID_ID, second, started_at=NOW)                            # learning
    store.add_answer(KID_ID, second, "k", False, True, None, __import__("datetime").date(2026, 11, 2))   # answered last: the owl goes here
    with running(app) as url:
        page = path_page(browser, url, scheme)
        assert page.locator(".orbit").count() == 2 and page.locator(f"#lesson-{two}, #lesson-{three}").count() == 2
        for skill, state in ((first, "mastered"), (second, "learning")):
            text = page.inner_text(f".star[data-skill='{skill}'] .lbl")
            assert WORDS[state] in text and {"mastered": "✓", "learning": "◐"}[state] in text
        third = next(s["id"] for s in bank.skills if s["unit"] == three)
        assert WORDS["not_started"] in page.inner_text(f".star[data-skill='{third}'] .lbl") and "○" in page.inner_text(f".star[data-skill='{third}'] .lbl")
        look = lambda skill: page.evaluate("(id) => { const n = document.querySelector(`.star[data-skill='${id}'] .node`); const s = getComputedStyle(n);"
                                           " return [s.borderTopColor, s.backgroundImage + s.backgroundColor]; }", skill)
        assert look(first) != look(second) != look(third) and look(first) != look(third)      # three different looks
        assert page.locator(".star.next").count() == 1 and page.get_attribute(".star.next", "data-skill") == second
        assert page.locator(".star.next .perch .sky-owl").count() == 1
        assert "ממשיכים כאן" in page.inner_text(".star.next .lbl")
        assert "1 מתוך 2 נשלטו" in page.inner_text(f"#lesson-{two} .hub")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_a_new_student_gets_the_owl_on_the_first_skill_and_everything_stays_open(browser, bank):
    two, three, _ = lessons_by_size(bank)
    app, _ = world(bank, [two, three])
    with running(app) as url:
        page = path_page(browser, url)
        first = page.locator(".star").first.get_attribute("data-skill")
        assert page.get_attribute(".star.next", "data-skill") == first
        assert page.locator(".star[href]").count() == page.locator(".star").count()      # every star is a link: nothing is locked


def test_a_student_sees_only_the_lessons_of_their_class(browser, bank):
    two, _, _ = lessons_by_size(bank)
    app, _ = world(bank, [two])
    with running(app) as url:
        page = path_page(browser, url)
        assert page.locator(".orbit").count() == 1 and page.locator(f"#lesson-{two}").count() == 1


# --- 4.3 access ---

def test_every_star_is_reached_with_tab_and_opened_with_enter_and_names_its_number_name_and_state(browser, bank):
    two, _, _ = lessons_by_size(bank)
    app, _ = world(bank, [two])
    with running(app) as url:
        page = path_page(browser, url)
        skills = [s for s in bank.skills if s["unit"] == two]
        for i, skill in enumerate(skills, 1):
            assert page.get_attribute(f".star[data-skill='{skill['id']}']", "aria-label").startswith(f"{i}. {skill['name']}: ")
        page.focus("#out")                                                           # start before the path, then Tab onwards
        reached = []
        for _ in range(40):
            page.keyboard.press("Tab")
            on = page.evaluate("document.activeElement.classList.contains('star') ? document.activeElement.dataset.skill : null")
            if on and on not in reached:
                reached.append(on)
            if len(reached) == len(skills):
                break
        assert reached == [s["id"] for s in skills]                                  # in order, by keyboard
        page.keyboard.press("Enter")
        assert page.evaluate("location.hash") == f"#/skill/{skills[-1]['id']}"


def test_nothing_on_the_path_animates_when_the_device_asks_for_less_motion(browser, bank):
    two, _, _ = lessons_by_size(bank)
    app, _ = world(bank, [two])
    with running(app) as url:
        page = path_page(browser, url)
        assert page.evaluate("document.getAnimations().length") > 0                    # the owl blinks and the next star pulses
        page.emulate_media(reduced_motion="reduce")
        assert page.evaluate("document.getAnimations().length") == 0


# --- 7.3 choosing a subject ---

def test_after_sign_in_the_student_sees_the_math_card_then_the_path_and_can_go_back(browser, bank):
    two, three, _ = lessons_by_size(bank)
    app, store = world(bank, [two, three])
    first = next(s["id"] for s in bank.skills if s["unit"] == two)
    store.save_progress(KID_ID, first, started_at=NOW, mastered_at=NOW)
    total = sum(1 for s in bank.skills if s["unit"] in (two, three))
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url)
        page.fill("#email", KID)
        page.click("#dev button")
        page.wait_for_selector(".subject-card")
        assert page.locator(".orbit").count() == 0 and page.locator(".subject-card").count() == 1      # the subjects first, no path yet
        assert "מתמטיקה כיתה ט - מצוינות" in page.inner_text(".subject-card") and f"1 מתוך {total} מיומנויות" in page.inner_text(".subject-card")
        assert page.get_attribute(".subject-card [role=progressbar]", "aria-valuenow") == "1"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        page.click(".subject-card")
        page.wait_for_selector(".tabs")                                                              # the card opens the subject's home
        assert page.evaluate("location.hash") == "#/subject/math" and page.locator(".orbit").count() == 0
        page.click(".tabs a[href='#/subject/math/path']")
        page.wait_for_selector(".orbit")
        assert page.evaluate("location.hash") == "#/subject/math/path"
        page.click("#to-subjects")                                                                    # a way back to the subjects
        page.wait_for_selector(".subject-card")
        assert page.locator(".orbit").count() == 0


def test_a_link_to_a_skill_opens_the_math_path_with_its_sheet(browser, bank):
    two, _, _ = lessons_by_size(bank)
    app, _ = world(bank, [two])
    skill = next(s["id"] for s in bank.skills if s["unit"] == two)
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(f"{url}#/skill/{skill}")
        page.fill("#email", KID)
        page.click("#dev button")
        page.wait_for_selector(".mx-sheet #ex-q")
        assert page.locator("#path").count() == 1 and page.locator(".subject-card").count() == 0


# --- add-rewards 1.1: the goal and the streak are on the path ---

def test_the_path_shows_todays_goal_and_the_streak(browser, bank):
    two, _, _ = lessons_by_size(bank)
    app, store = world(bank, [two])
    skill = next(s["id"] for s in bank.skills if s["unit"] == two)
    from mathly2 import clock
    for i in range(3):
        store.add_answer(KID_ID, skill, f"k{i}", True, True, None, clock.school_day())
    with running(app) as url:
        page = path_page(browser, url)
        assert "יעד יומי: 3 מתוך 5" in page.inner_text("#goal-text") and "רצף: 0" in page.inner_text("#streak")
        assert page.get_attribute("#goal [role=progressbar]", "aria-valuenow") == "3"


# --- add-rewards 2.3: a faded star ---

def test_a_faded_star_is_dimmed_says_fading_and_still_counts_as_mastered(browser, bank):
    from datetime import timedelta
    from mathly2 import clock
    two, _, _ = lessons_by_size(bank)
    app, store = world(bank, [two])
    first, second = [s["id"] for s in bank.skills if s["unit"] == two][:2]
    for skill in (first, second):
        store.save_progress(KID_ID, skill, started_at=NOW, mastered_at=NOW)
    store.add_answer(KID_ID, first, "k", True, True, None, clock.school_day() - timedelta(days=20))      # faded
    store.add_answer(KID_ID, second, "k", True, True, None, clock.school_day() - timedelta(days=1))      # bright
    with running(app) as url:
        page = path_page(browser, url)
        faded, bright = f".star[data-skill='{first}']", f".star[data-skill='{second}']"
        assert "דועך" in page.inner_text(faded + " .lbl") and "◌" in page.inner_text(faded + " .lbl")
        assert "דועך" in page.get_attribute(faded, "aria-label") and "נשלטה" in page.get_attribute(faded, "aria-label")
        assert "דועך" not in page.inner_text(bright + " .lbl")
        look = lambda sel: page.evaluate("(s) => getComputedStyle(document.querySelector(s + ' .node')).opacity", sel)
        assert look(faded) != look(bright)
        assert "2 מתוך" in page.inner_text(f"#lesson-{two} .hub")              # fading does not change what counts
        # one answer on it relights the star
        store.add_answer(KID_ID, first, "k2", False, True, None, clock.school_day())
        page.reload()
        page.wait_for_selector(".orbit")
        assert "דועך" not in page.inner_text(faded + " .lbl")


# --- after Google sign-in the address holds the token: the student still lands on the subjects ---

def test_an_oauth_fragment_in_the_address_does_not_skip_the_subject_cards(browser, bank):
    two, _, _ = lessons_by_size(bank)
    app, _ = world(bank, [two])
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url + "#access_token=abc.def.ghi&expires_in=3600&token_type=bearer")        # what the sign-in service sends the browser back with
        page.fill("#email", KID)
        page.click("#dev button")
        page.wait_for_selector(".subject-card")
        assert page.locator(".orbit").count() == 0
