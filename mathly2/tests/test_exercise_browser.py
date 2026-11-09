"""The exercise screen in a real browser: the sheet over the path, tap to answer, help, chips, resuming, closing, and the board."""
import copy
import uuid
from datetime import date

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.bank import Bank, load_bank, question_key
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running

KID, MGR, DEV = "kid@school.test", "mgr@school.test", "dev@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))
PHONE, DESKTOP = {"width": 390, "height": 844}, {"width": 1280, "height": 800}
SOLVED = {"question": "$x² + 5x + 6$", "answer": "$(x + 2)(x + 3)$",
          "steps": [{"do": "מוצאים 2 ו־3", "why": "המכפלה 6 והסכום 5"}, {"do": "כותבים $(x + 2)(x + 3)$", "why": "כך מפרקים"}]}
LONG_AGO = date(2020, 1, 1)


@pytest.fixture(scope="module")
def raw():
    return copy.deepcopy(load_bank().data)


@pytest.fixture
def world(raw):
    data = copy.deepcopy(raw)
    plain = [s for s in data["skills"] if len(s.get("questions", [])) >= 4 and not s.get("prereqs")]
    bare, solved = plain[0]["id"], plain[1]["id"]
    for s in data["skills"]:
        if s["id"] == solved:
            s["worked_example"] = copy.deepcopy(SOLVED)
    bank = Bank(data)
    chained = next(s["id"] for s in bank.skills if s.get("prereqs") and s.get("questions"))
    store = InMemoryStore()
    store.give_role(MGR, "manager", "setup")
    store.add_member(store.create_class("setup", "A", lessons=[u["id"] for u in data["units"]])["id"], KID)
    app = create_app(Settings(developers=frozenset({DEV})), bank=bank, store=store)
    return app, store, bank, {"bare": bare, "solved": solved, "chained": chained}


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def sign_in(browser, url, where="", viewport=PHONE, email=KID):
    page = offline_formulas(browser.new_page(viewport=viewport))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + where)
    page.fill("#email", email)
    page.click("#dev button")
    if not where:                                   # the first screen is the subjects: open math
        page.click(".subject-card")
        page.click(".tabs a[href='#/subject/math/path']")
    page.errors = errors
    return page


def open_skill(browser, url, skill, **kw):
    page = sign_in(browser, url, f"#/skill/{skill}", **kw)
    page.wait_for_selector(".mx-sheet #ex-q")
    return page


def key_on_screen(page):
    return page.get_attribute("#ex-q", "data-key")


def choose(page, bank, skill, right=True):
    """Tap the right (or a wrong) choice of the question on screen; returns its bank position."""
    key = key_on_screen(page)
    question = next(q for q in bank.skill(skill)["questions"] if question_key(skill, q) == key)
    wanted = [i for i, c in enumerate(question["choices"]) if bool(c.get("correct")) == right]
    if not right:
        wanted = [i for i in wanted if question["choices"][i].get("mistake")] or wanted
    page.click(f"#ex-choices .ex-choice[data-i='{wanted[0]}']")
    return wanted[0]


# --- 5.1 the sheet ---

def test_opening_a_skill_shows_the_sheet_over_the_path_with_its_parts(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        skill = bank.skill(ids["bare"])
        assert page.locator("#path").count() == 1                                  # the path is still there under the sheet
        assert page.get_attribute(".mx-sheet", "role") == "dialog" and page.get_attribute(".mx-sheet", "aria-modal") == "true"
        lesson = next(l for l in bank.lessons if l["id"] == skill["unit"])
        head = page.inner_text(".mx-shtop")
        assert lesson["name"] in head and skill["name"] in head
        assert page.locator("[data-board-toggle]").count() == 1 and page.locator("[data-help]").count() == 1 and page.locator(".mx-x").count() == 1
        assert skill["description"] in page.inner_text(".ex-explain")
        total = len(bank.practice_keys(skill["id"]))                              # practice uses at most 10 questions per skill
        assert page.inner_text("#ex-count") == f"שאלה 1 מתוך {total}" and page.locator("#ex-dots i").count() == total
        assert page.locator("#ex-q .ex-text").count() == 1 and page.locator("#ex-choices .ex-choice").count() >= 2
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth") and page.errors == []


def test_choices_come_in_a_new_order_and_the_server_grades_by_their_bank_position(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        shuffles = page.evaluate("import('/static/ui.js').then(m => Array.from({length: 12}, () => m.shuffled([0, 1, 2, 3]).join()))")
        assert len(set(shuffles)) > 1                                              # not always the same order
        shown = page.eval_on_selector_all("#ex-choices .ex-choice", "els => els.map(e => Number(e.dataset.i))")
        assert sorted(shown) == list(range(len(shown)))                            # every bank position, once
        choose(page, bank, ids["bare"], right=True)
        page.wait_for_selector("#ex-fb .ex-ok")                                    # graded right whatever the order on screen


# --- 5.2 right and wrong answers ---

def test_a_right_answer_celebrates_counts_and_goes_on_after_a_countdown_that_can_be_skipped(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        first = key_on_screen(page)
        choose(page, bank, ids["bare"], right=True)
        page.wait_for_selector("#ex-fb .ex-ok")
        assert "נכון ✓" in page.inner_text("#ex-fb") and "1 תשובה נכונה ברצף" in page.inner_text("#ex-fb")
        assert page.locator(".ex-choice.right").count() == 1 and page.locator(".ex-choice .burst").count() == 1
        assert "בעוד" in page.inner_text("#ex-countdown")
        assert page.locator("#ex-dots i.ok").count() == 1 and "שאלה 2 מתוך" in page.inner_text("#ex-count")
        page.click("#ex-skip")
        page.wait_for_function("(k) => document.getElementById('ex-q').dataset.key !== k", arg=first)
        assert page.locator(".ex-choice.right").count() == 0 and page.locator("#ex-fb").inner_text().strip() == ""


def test_the_countdown_moves_on_by_itself_and_can_be_stopped(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        first = key_on_screen(page)
        choose(page, bank, ids["bare"])
        page.wait_for_function("(k) => document.getElementById('ex-q').dataset.key !== k", arg=first, timeout=8000)    # by itself
        second = key_on_screen(page)
        choose(page, bank, ids["bare"])
        page.click("#ex-pause")
        page.wait_for_timeout(3600)
        assert key_on_screen(page) == second and page.locator("#ex-fb .ex-ok").count() == 1                            # stopped: it stays


def test_a_wrong_answer_is_quiet_names_the_mistake_never_marks_the_right_choice_and_gives_another_question(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        first = key_on_screen(page)
        question = next(q for q in bank.skill(ids["bare"])["questions"] if question_key(ids["bare"], q) == first)
        wrong = choose(page, bank, ids["bare"], right=False)
        page.wait_for_selector("#ex-fb .ex-bad")
        mistake = bank.mistakes[question["choices"][wrong]["mistake"]]
        assert mistake["name"] in page.inner_text("#ex-fb .ex-bad")
        assert page.locator(".ex-choice.wrong").count() == 1 and page.locator(".ex-choice.right").count() == 0     # the right one is not shown
        assert page.locator("#ex-countdown").count() == 0 and page.locator(".ex-choice .burst").count() == 0
        assert page.locator("#ex-returns").count() == 0 and page.inner_text("#ex-other") == "לשאלה הבאה"          # a wrong question does not come back
        page.click("#ex-other")
        page.wait_for_function("(k) => document.getElementById('ex-q').dataset.key !== k", arg=first)


def test_a_mistake_that_names_a_skill_to_go_back_to_links_to_it(browser, world):
    app, store, bank, _ = world
    skill_id, question, index = next((s["id"], q, i) for s in bank.skills for q in s.get("questions", [])
                                     for i, c in enumerate(q["choices"]) if c.get("mistake") and bank.mistakes[c["mistake"]].get("back"))
    store.save_progress(KID_ID, skill_id, current_key=question_key(skill_id, question))
    back = bank.mistakes[question["choices"][index]["mistake"]]["back"]
    with running(app) as url:
        page = open_skill(browser, url, skill_id)
        page.click(f"#ex-choices .ex-choice[data-i='{index}']")
        page.wait_for_selector("#ex-fb .ex-bad a")
        assert page.get_attribute("#ex-fb .ex-bad a", "href") == f"#/skill/{back}"
        page.click("#ex-fb .ex-bad a")
        page.wait_for_function("(t) => document.getElementById('ex-title').innerText.includes(t)", arg=bank.skill(back)["name"])


def test_mastering_a_skill_is_announced_and_marked(browser, world):
    app, store, bank, ids = world
    skill = ids["bare"]
    key = bank.question_keys(skill)[0]
    store.save_progress(KID_ID, skill, started_at="then", current_key=key)
    for n in (1, 2):
        store.add_answer(KID_ID, skill, f"old{n}", True, True, None, LONG_AGO)       # two right answers long ago, today the third
    with running(app) as url:
        page = open_skill(browser, url, skill)
        choose(page, bank, skill)
        page.wait_for_selector("#ex-mastered")
        assert "המיומנות נשלטה" in page.inner_text("#ex-mastered") and page.locator(".ex-done").count() == 1


# --- 5.3 help and related skills ---

def test_help_shows_the_explanation_and_a_solved_example_only_when_there_is_one_and_the_answer_does_not_count(browser, world):
    app, store, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        assert page.is_hidden("#ex-helpbox")
        page.click("[data-help]")
        page.wait_for_selector("#ex-helpbox", state="visible")
        assert bank.skill(ids["bare"])["description"] in page.inner_text("#ex-helpbox") and "דוגמה פתורה" not in page.inner_text("#ex-helpbox")
        assert "לא תיספר לשליטה" in page.inner_text("#ex-helpbox")
        choose(page, bank, ids["bare"])
        page.wait_for_selector("#ex-fb .ex-ok")
        assert store.last_counted_answers(KID_ID, ids["bare"], 5) == []              # stored, but not counted toward mastery
        assert store.answer_counts(KID_ID, ids["bare"])                              # it was stored
        page2 = open_skill(browser, url, ids["solved"])
        page2.click("[data-help]")
        text = page2.inner_text("#ex-helpbox")
        assert "דוגמה פתורה" in text and "מוצאים 2 ו־3" in text and "המכפלה 6 והסכום 5" in text and "תשובה:" in text


def test_related_skills_are_chips_that_open_that_skill(browser, world):
    app, _, bank, ids = world
    skill = bank.skill(ids["chained"])
    needed = bank.skill(skill["prereqs"][0])
    with running(app) as url:
        page = open_skill(browser, url, ids["chained"])
        assert needed["name"] in page.inner_text(".ex-related")
        page.click(f".ex-related a[href='#/skill/{needed['id']}']")
        page.wait_for_function("(t) => document.getElementById('ex-title').innerText.includes(t)", arg=needed["name"])
        assert page.locator("#path").count() == 1 and page.locator(".mx-sheet").count() == 1       # still one sheet over the path


# --- 5.4 resuming and stale answers ---

def test_reopening_a_skill_continues_with_the_question_that_was_on_screen(browser, world):
    app, _, _, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        key = key_on_screen(page)
        page.click(".mx-x")
        page.wait_for_selector(".mx-layer", state="detached")
        page.click(f".star[data-skill='{ids['bare']}']")
        page.wait_for_selector("#ex-q")
        assert key_on_screen(page) == key


def test_an_answer_for_a_question_another_tab_replaced_shows_the_current_question(browser, world):
    app, store, bank, ids = world
    with running(app) as url:
        first = open_skill(browser, url, ids["bare"])
        stale = key_on_screen(first)
        store.save_progress(KID_ID, ids["bare"], current_key=next(k for k in bank.question_keys(ids["bare"]) if k != stale))   # another tab moved on
        choose(first, bank, ids["bare"], right=True)
        first.wait_for_selector(".ex-note")
        assert "התחלפה" in first.inner_text(".ex-note") and key_on_screen(first) == store.get_progress(KID_ID, ids["bare"])["current_key"]
        assert store.answer_counts(KID_ID, ids["bare"]) == {}                         # the stale answer was not stored


def test_a_skill_with_no_questions_says_so(browser, world):
    app, _, _, _ = world
    with running(app) as url:
        page = sign_in(browser, url, "#/skill/a_30_side")
        page.wait_for_selector("#no-practice")
        assert "אין עדיין שאלות תרגול" in page.inner_text(".mx-sheet") and page.locator("#ex-choices").count() == 0


# --- 5.5 closing, links, the board ---

def test_closing_the_sheet_shows_the_updated_star_and_escape_and_the_scrim_close_it_too(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = sign_in(browser, url)
        page.wait_for_selector(".star")
        page.click(f".star[data-skill='{ids['bare']}']")
        page.wait_for_selector("#ex-q")
        assert page.evaluate("location.hash") == f"#/skill/{ids['bare']}"
        choose(page, bank, ids["bare"])
        page.wait_for_selector("#ex-fb .ex-ok")
        page.click(".mx-x")
        page.wait_for_selector(".mx-layer", state="detached")
        assert page.evaluate("location.hash") == "#/subject/math/path"
        page.wait_for_function("(id) => document.querySelector(`.star[data-skill='${id}'] .lbl`).innerText.includes('בלמידה')", arg=ids["bare"])   # the star shows its new state
        assert page.get_attribute(".star.next", "data-skill") == ids["bare"]                           # and the owl is on it
        page.click(f".star[data-skill='{ids['bare']}']")
        page.wait_for_selector("#ex-q")
        page.keyboard.press("Escape")
        page.wait_for_selector(".mx-layer", state="detached")
        page.click(f".star[data-skill='{ids['bare']}']")
        page.wait_for_selector("#ex-q")
        page.mouse.click(2, 2)                                                                          # the scrim
        page.wait_for_selector(".mx-layer", state="detached")


def test_a_link_and_a_reload_open_the_sheet_over_the_path(browser, world):
    app, _, _, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        page.reload()
        page.wait_for_selector(".mx-sheet #ex-q")
        assert page.locator(".trail .star").count() > 0


def test_switching_role_or_signing_out_takes_the_sheet_away(browser, world):
    """A modal sheet covers the header, so a person cannot reach these buttons with the mouse while it is open; the shell still
    closes it if the role changes or the person signs out some other way (a script click stands in for that)."""
    app, _, _, ids = world
    with running(app) as url:
        page = sign_in(browser, url, f"#/skill/{ids['bare']}", email=DEV)
        page.wait_for_selector(".mx-sheet #ex-q")
        page.evaluate("document.querySelector('#nav [data-role=manager]').click()")
        page.wait_for_selector("#mgr")
        assert page.locator(".mx-layer").count() == 0
        page.click("#nav [data-role='student']")
        page.click(".subject-card")
        page.click(".tabs a[href='#/subject/math/path']")
        page.wait_for_selector("#path")
        page.click(".star >> nth=0")
        page.wait_for_selector(".mx-sheet")
        page.evaluate("document.getElementById('out').click()")
        page.wait_for_selector("#signin")
        assert page.locator(".mx-layer").count() == 0


def test_the_board_opens_from_the_sheet_beside_it_on_a_desktop_with_a_sketch_per_question(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"], viewport=DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        board, sheet = page.locator(".mx-board").bounding_box(), page.locator(".mx-sheet").bounding_box()
        assert board["x"] + board["width"] <= sheet["x"] + 2
        blank = page.evaluate("document.querySelector('.mx-board canvas').toDataURL()")       # the question is already at the top
        ink = """() => { const c = document.querySelector('.mx-board canvas'), d = c.getContext('2d').getImageData(0, 0, c.width, Math.min(c.height, 260)).data;
                         let n = 0; for (let i = 0; i < d.length; i += 4) if (d[i + 3] && (d[i] < 200 || d[i + 1] < 200 || d[i + 2] < 200)) n++; return n; }"""
        assert page.evaluate(ink) > 50                                                          # the question's words are on the board by themselves
        box = page.locator(".mx-board canvas").bounding_box()
        page.mouse.move(box["x"] + 60, box["y"] + 150)
        page.mouse.down()
        page.mouse.move(box["x"] + 200, box["y"] + 220, steps=8)
        page.mouse.up()
        drawn = page.evaluate("document.querySelector('.mx-board canvas').toDataURL()")
        assert drawn != blank
        choose(page, bank, ids["bare"])
        page.click("#ex-skip")
        page.wait_for_function("(b) => document.querySelector('.mx-board canvas').toDataURL() !== b", arg=drawn)         # the next question: no stroke of the last one
        assert page.evaluate(ink) > 50                                                                              # and its own question at the top
        assert page.locator(".mx-board").count() == 1 and page.get_attribute("[data-board-toggle]", "aria-pressed") == "true"


def test_on_a_phone_the_board_covers_the_screen_and_returns_to_the_same_question(browser, world):
    app, _, _, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"], viewport=PHONE)
        key = key_on_screen(page)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board.full")
        page.click(".mx-board-back")
        page.wait_for_function("document.querySelector('.mx-board') === null")
        assert key_on_screen(page) == key and page.locator(".mx-sheet").count() == 1


def test_a_skill_with_thirty_questions_says_question_n_of_ten_in_the_browser(browser, world):
    app, _, bank, _ = world
    big = next(s["id"] for s in bank.skills if len(s.get("questions", [])) == 30)
    with running(app) as url:
        page = open_skill(browser, url, big)
        assert page.inner_text("#ex-count") == "שאלה 1 מתוך 10" and page.locator("#ex-dots i").count() == 10


# --- show-answer-pending: the thinking indicator ---

def test_a_tapped_choice_shows_it_is_being_checked_until_the_slow_answer_arrives(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        held = []
        page.route("**/api/skills/*/answer", lambda route: held.append(route))   # the answer request is held back until the test lets it go
        key = key_on_screen(page)
        question = next(q for q in bank.skill(ids["bare"])["questions"] if question_key(ids["bare"], q) == key)
        right = next(i for i, c in enumerate(question["choices"]) if c.get("correct"))
        other = next(i for i, c in enumerate(question["choices"]) if not c.get("correct"))
        page.click(f"#ex-choices .ex-choice[data-i='{right}']")
        page.wait_for_selector("#ex-thinking")
        assert "בודקים" in page.inner_text("#ex-fb")                           # the line, and the tapped choice spins
        tapped = page.locator(f"#ex-choices .ex-choice[data-i='{right}']")
        assert "pending" in tapped.get_attribute("class") and tapped.get_attribute("aria-busy") == "true"
        assert page.evaluate("(i) => getComputedStyle(document.querySelector(`.ex-choice[data-i='${i}']`), '::after').animationName", right) == "ex-spin"
        faded = page.locator(f"#ex-choices .ex-choice[data-i='{other}']")
        assert faded.is_disabled() and "dim" in faded.get_attribute("class")      # the others step back and cannot be tapped
        held[0].continue_()                                                   # the answer arrives
        page.wait_for_selector("#ex-fb .ex-ok")
        assert page.locator("#ex-thinking").count() == 0 and page.locator(".ex-choice.pending, .ex-choice.dim").count() == 0
        assert "right" in page.locator(f"#ex-choices .ex-choice[data-i='{right}']").get_attribute("class")


def test_the_indicator_has_words_and_a_still_spinner_with_reduced_motion(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE, reduced_motion="reduce"))
        page.goto(f"{url}#/skill/{ids['bare']}")
        page.fill("#email", KID)
        page.click("#dev button")
        page.wait_for_selector(".mx-sheet #ex-q")
        held = []
        page.route("**/api/skills/*/answer", lambda route: held.append(route))
        page.click("#ex-choices .ex-choice >> nth=0")
        page.wait_for_selector("#ex-thinking")
        assert "בודקים" in page.inner_text("#ex-fb")
        assert page.evaluate("document.getAnimations().filter(a => a.animationName === 'ex-spin').length") == 0       # words, but no turning
        held[0].continue_()
        page.wait_for_selector("#ex-fb .ex-ok, #ex-fb .ex-bad")


def test_after_an_error_the_indicator_goes_and_the_choices_work_again(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        page.route("**/api/skills/*/answer", lambda route: route.fulfill(status=500, body='{"detail": "x"}', content_type="application/json"))
        page.click("#ex-choices .ex-choice >> nth=0")
        page.wait_for_selector("#ex-fb [role=alert]")
        assert page.locator("#ex-thinking").count() == 0 and page.locator(".ex-choice.pending, .ex-choice.dim").count() == 0
        assert page.locator("#ex-choices .ex-choice:disabled").count() == 0


# --- mark-wrong-choice ---

def test_a_wrong_answer_marks_only_the_chosen_choice_with_a_word_and_a_symbol(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        wrong = choose(page, bank, ids["bare"], right=False)
        page.wait_for_selector("#ex-fb .ex-bad")
        chosen = page.locator(f"#ex-choices .ex-choice[data-i='{wrong}']")
        assert "wrong" in chosen.get_attribute("class") and "✗ לא נכון" in chosen.inner_text()               # the word is part of the choice, so a screen reader reads it
        assert page.locator("#ex-choices .verdict").count() == 1                              # nothing else carries a label
        assert page.locator("#ex-choices .ex-choice.wrong").count() == 1 and page.locator("#ex-choices .ex-choice.right").count() == 0
        width = page.evaluate("(i) => getComputedStyle(document.querySelector(`.ex-choice[data-i='${i}']`)).borderTopWidth", wrong)
        assert width == "3px"                                                                  # a stronger border than the 2px of the others
        assert page.locator("#ex-choices .ex-choice:not(.wrong)").first.evaluate("e => getComputedStyle(e).borderTopWidth") == "2px"


# --- ten-question-rounds ---

def next_after(page):
    """Move on after an answer: the right answer's "next" or the wrong answer's "next" (or the result after the last)."""
    page.click("#ex-skip, #ex-other, #ex-results")


def play(page, bank, skill, rights):
    for n, ok in enumerate(rights):
        choose(page, bank, skill, right=ok)
        page.wait_for_selector("#ex-fb .ex-ok, #ex-fb .ex-bad")
        key = key_on_screen(page)
        next_after(page)
        if n < len(rights) - 1:
            page.wait_for_function("(k) => document.querySelector('#ex-q')?.dataset.key !== k", arg=key)


def test_the_dots_fill_for_right_and_are_marked_for_wrong_and_the_counter_follows_the_round(browser, world):
    app, _, bank, ids = world
    with running(app) as url:
        page = open_skill(browser, url, ids["bare"])
        assert page.inner_text("#ex-count") == "שאלה 1 מתוך 10" and page.locator("#ex-dots i").count() == 10
        play(page, bank, ids["bare"], [True, False])
        page.wait_for_selector("#ex-q")
        assert page.inner_text("#ex-count") == "שאלה 3 מתוך 10"
        assert page.locator("#ex-dots i.ok").count() == 1 and page.locator("#ex-dots i.bad").count() == 1
        assert page.locator("#ex-dots i.bad").inner_text() == "✗"
        assert "1 נכונות" in page.get_attribute("#ex-dots", "aria-label") or "נענו 2 מתוך 10" in page.get_attribute("#ex-dots", "aria-label")


def test_ten_answers_end_the_round_with_a_result_that_survives_a_reload_and_a_new_round_starts_again(browser, world):
    app, _, bank, ids = world
    skill = ids["bare"]
    rights = [True, True, False, True, False, True, True, True, False, True]            # 7 right, 3 wrong
    with running(app) as url:
        page = open_skill(browser, url, skill)
        play(page, bank, skill, rights)
        page.wait_for_selector("#ex-round")
        assert page.inner_text("#ex-score").replace("\n", " ").split()[:3] == ["7", "מתוך", "10"] and page.locator("#ex-q").count() == 0
        assert page.locator("#ex-missed li").count() == 3 and page.inner_text("#ex-count") == "הסבב הסתיים"
        assert page.locator("#ex-dots i.ok").count() == 7 and page.locator("#ex-dots i.bad").count() == 3
        assert page.locator("#ex-round .right, #ex-round [data-correct]").count() == 0                       # no right answer is shown
        page.reload()                                                                                         # the result is still there
        page.wait_for_selector("#ex-round")
        assert page.locator("#ex-score b").inner_text() == "7"
        page.click("#ex-newround")                                                                            # a new round: ten again, empty dots
        page.wait_for_selector("#ex-q")
        assert page.inner_text("#ex-count") == "שאלה 1 מתוך 10" and page.locator("#ex-dots i.ok, #ex-dots i.bad").count() == 0


def test_a_wrong_question_is_not_shown_again_in_the_round_in_the_browser(browser, world):
    app, _, bank, ids = world
    skill = ids["bare"]
    with running(app) as url:
        page = open_skill(browser, url, skill)
        shown = []
        for n in range(10):
            shown.append(key_on_screen(page))
            choose(page, bank, skill, right=(n % 2 == 0))
            page.wait_for_selector("#ex-fb .ex-ok, #ex-fb .ex-bad")
            next_after(page)
            if n < 9:
                page.wait_for_function("(k) => document.querySelector('#ex-q')?.dataset.key !== k", arg=shown[-1])
        assert len(set(shown)) == 10                                                                           # each question once, none came back
        page.wait_for_selector("#ex-round")
