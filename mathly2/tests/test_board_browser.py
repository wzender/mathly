"""The smart board (copied from mathly1) in a real browser: its layout, tools, drawing, sketches and calculator.
The board is hosted in a small sheet built here, the same contract the exercise screen follows:
.mx-layer > .mx-sheet with a [data-board-toggle] button, and MathlyBoard.mount(layer, key, {question})."""
import hashlib
import re
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.main import create_app
from mathly2.tests.serve import offline_formulas, running

STATIC = Path(__file__).parent.parent / "static"
COPIED = {   # copied from mathly1 and not edited here (math-board.js is mathly2's own now: the right-button eraser and the question placed by itself)
    "board-math.js": "613e642f762a9ca8276c2192bf43d0a8cf7a606bf06f29f01b54b3a19747a579",}
PHONE, DESKTOP = {"width": 390, "height": 844}, {"width": 1280, "height": 800}
TOOLS = {"move": "הזזה", "pen": "עט", "line": "קו ישר", "circle": "עיגול", "angle": "זווית", "math": "נוסחה", "eraser": "מחק"}
HOST = """async (key) => {
  const layer = document.createElement('div'); layer.className = 'mx-layer'; layer.id = 'host';
  layer.innerHTML = '<div class="mx-scrim"></div><div class="mx-sheet" role="dialog" aria-modal="true"><div class="mx-shacts">' + MathlyBoard.button() +
    '</div><div class="mx-q" id="q1"><p>(x + 3)(x − 5) = ?</p></div><div class="mx-q" id="q2"><p>x² − 9 = ?</p></div></div>';
  document.body.append(layer);
  window.mountFor = (k, id) => MathlyBoard.mount(layer, k, { question: () => layer.querySelector('#' + id) });
  layer.querySelector('[data-board-toggle]').addEventListener('click', () => MathlyBoard.toggle());
  window.mountFor(key, 'q1');
}"""


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def board_page(browser, url, viewport, scheme="light", requests=None):
    page = offline_formulas(browser.new_page(viewport=viewport, color_scheme=scheme))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" and "mathjax" not in m.text.lower() and "ERR_FAILED" not in m.text else None)
    if requests is not None:
        page.on("request", lambda r: requests.append(r.url))
    page.goto(url)
    page.wait_for_selector("#signin")
    page.add_style_tag(url="/static/board.css")
    page.add_script_tag(url="/static/board-math.js")
    page.add_script_tag(url="/static/math-board.js")
    page.evaluate(HOST, "skill:q1")
    page.errors = errors
    return page


def png(page):
    return page.evaluate("document.querySelector('.mx-board canvas').toDataURL()")


def draw_line(page, dx=120, dy=60):
    box = page.locator(".mx-board canvas").bounding_box()
    x, y = box["x"] + 60, box["y"] + 120
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x + dx / 2, y + dy / 2, steps=5)
    page.mouse.move(x + dx, y + dy, steps=5)
    page.mouse.up()


# --- 3.1 the copied files ---

def test_the_math_keyboard_file_is_the_unedited_copy_from_mathly1():
    for name, digest in COPIED.items():
        assert hashlib.sha256((STATIC / name).read_bytes()).hexdigest() == digest, f"{name} was edited: copy it from mathly1 again"
    assert (STATIC / "vendor" / "mathlive" / "mathlive.min.js").stat().st_size > 100_000


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_the_board_loads_and_opens_in_light_and_dark_with_no_error(browser, scheme):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP, scheme)
        assert page.evaluate("Object.keys(window.MathlyBoard).sort()") == ["button", "closeFull", "desk", "hasWork", "isOn", "mount", "openFull", "pictureOf", "show", "toggle", "workSig"]
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board")
        assert page.is_visible(".mx-board") and page.is_visible(".mx-board-bar")
        background = page.evaluate("getComputedStyle(document.querySelector('.mx-board')).backgroundColor")
        assert background not in ("", "rgba(0, 0, 0, 0)")
        assert page.errors == []


# --- 3.2 the board's behaviour ---

def test_on_a_phone_the_board_covers_the_screen_and_closes_back_to_the_question(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, PHONE)
        assert page.evaluate("MathlyBoard.desk()") is False and page.locator(".mx-board").count() == 0
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board.full")
        box = page.locator(".mx-board").bounding_box()
        assert box["width"] >= PHONE["width"] - 2 and box["height"] >= PHONE["height"] - 2
        assert page.get_attribute(".mx-board", "role") == "dialog"
        page.click(".mx-board .mx-board-back")
        page.wait_for_function("document.querySelector('.mx-board') === null")
        assert page.is_visible("#q1")                                            # the same question is still there


def test_on_a_desktop_the_board_sits_beside_the_sheet(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        assert page.evaluate("MathlyBoard.desk()") is True
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board")
        board, sheet = page.locator(".mx-board").bounding_box(), page.locator(".mx-sheet").bounding_box()
        assert board["x"] + board["width"] <= sheet["x"] + 2                       # the board ends where the sheet starts
        assert page.evaluate("document.querySelector('.mx-sheet').classList.contains('with-board')")
        assert page.get_attribute(".mx-sheet", "aria-modal") is None               # the board is outside the dialog: still reachable
        page.click(".mx-board .mx-board-close")
        page.wait_for_function("document.querySelector('.mx-board') === null")
        assert page.get_attribute("[data-board-toggle]", "aria-pressed") == "false"


def test_every_tool_has_a_hebrew_label_and_an_icon(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board")
        for tool, name in TOOLS.items():
            button = page.locator(f".mx-board [data-tool='{tool}']")
            assert button.get_attribute("title") == name and button.locator("svg").count() == 1
        for action, name in {"calc": "מחשבון", "question": "השאלה", "undo": "ביטול", "clear": "ניקוי"}.items():
            assert name in page.inner_text(f".mx-board [data-do='{action}']") or page.get_attribute(f".mx-board [data-do='{action}']", "title")
        assert page.get_attribute(".mx-board .mx-board-close", "aria-label") == "סגירת הלוח"
        assert page.locator(".mx-board [data-ink]").count() == 3                    # three ink colours


def test_a_pen_stroke_changes_the_canvas_and_undo_brings_it_back(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        blank = png(page)
        draw_line(page)
        drawn = png(page)
        assert drawn != blank
        page.click(".mx-board [data-do='undo']")
        assert png(page) == blank
        draw_line(page)
        page.click(".mx-board [data-do='clear']")
        assert png(page) == blank                                                   # the work goes; the question stays (it is in `blank` too)


def test_the_eraser_removes_a_stroke_it_touches(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        blank = png(page)
        draw_line(page)
        assert png(page) != blank
        page.click(".mx-board [data-tool='eraser']")
        box = page.locator(".mx-board canvas").bounding_box()
        x, y = box["x"] + 60, box["y"] + 120
        page.mouse.move(x - 10, y - 10)
        page.mouse.down()
        page.mouse.move(x + 60, y + 30, steps=12)
        page.mouse.move(x + 130, y + 70, steps=12)
        page.mouse.up()
        page.click(".mx-board [data-tool='pen']")
        assert png(page) == blank                                                   # the stroke is gone


def test_the_questions_copy_stays_when_the_eraser_passes_over_it(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        blank = png(page)
        page.click(".mx-board [data-do='question']")
        page.wait_for_function("(b) => document.querySelector('.mx-board canvas').toDataURL() !== b", arg=blank)
        page.click(".mx-board [data-tool='pen']")                                    # a new copy is selected; changing tool lets go of it
        copied = png(page)
        assert copied != blank
        page.click(".mx-board [data-tool='eraser']")
        box = page.locator(".mx-board canvas").bounding_box()
        page.mouse.move(box["x"] + 10, box["y"] + 20)
        page.mouse.down()
        page.mouse.move(box["x"] + box["width"] - 10, box["y"] + 20, steps=10)
        page.mouse.move(box["x"] + box["width"] - 10, box["y"] + 80, steps=10)
        page.mouse.up()
        page.click(".mx-board [data-tool='pen']")                                    # the eraser's own cursor ring is not a mark
        assert png(page) == copied                                                  # the eraser leaves the copy alone


def test_each_question_keeps_its_own_sketch_and_nothing_is_sent_anywhere(browser):
    with running(create_app()) as url:
        requests = []
        page = board_page(browser, url, DESKTOP, requests=requests)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        blank = png(page)
        draw_line(page)
        first = png(page)
        sent_before = len([r for r in requests if "/api/" in r])
        page.evaluate("window.mountFor('skill:q2', 'q2')")
        page.wait_for_selector(".mx-board canvas")
        second = png(page)
        assert second != first and second != blank                                  # question 2 has its own question at the top and no stroke of question 1
        page.evaluate("window.mountFor('skill:q1', 'q1')")
        page.wait_for_selector(".mx-board canvas")
        assert png(page) == first                                                   # question 1's sketch is still there
        assert len([r for r in requests if "/api/" in r]) == sent_before            # the board sent nothing to the server


# --- 3.3 the calculator ---

def calc_press(page, *labels):
    """Press calculator keys by the label printed on them (each key holds its label in a <b>)."""
    for label in labels:
        page.locator(".mx-calc-keys button").filter(has=page.locator("b", has_text=re.compile(f"^{re.escape(label)}$"))).first.click()


def test_the_calculator_gives_sin_30_and_7_times_6(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board")
        assert page.is_hidden(".mx-calc")
        page.click(".mx-board [data-do='calc']")
        page.wait_for_selector(".mx-calc", state="visible")
        calc_press(page, "sin", "3", "0", ")", "=")
        assert page.inner_text("[data-calc-out]").strip() == "0.5"                    # degrees
        calc_press(page, "AC", "7", "×", "6", "=")
        assert page.inner_text("[data-calc-out]").strip() == "42"
        page.click(".mx-board [data-do='calc']")
        assert page.is_hidden(".mx-calc")


# --- board-question-and-right-click-eraser ---

def test_the_question_is_on_the_board_when_it_opens_and_each_question_has_its_own(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        first = png(page)
        empty = page.evaluate("""() => { const c = document.createElement('canvas'); const b = document.querySelector('.mx-board canvas'); c.width = b.width; c.height = b.height; return c.toDataURL(); }""")
        assert first != empty                                                       # something is drawn already: the question at the top
        page.evaluate("window.mountFor('skill:q2', 'q2')")
        page.wait_for_selector(".mx-board canvas")
        second = png(page)
        assert second != empty and second != first                                  # the other question, in its own board


def test_a_deleted_question_does_not_come_back_and_the_button_places_it_again(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        with_question = png(page)
        page.click(".mx-board [data-tool='move']")
        box = page.locator(".mx-board canvas").bounding_box()
        page.mouse.click(box["x"] + box["width"] - 60, box["y"] + 30)               # select the card at the top
        page.click(".mx-board [data-do='delete']")
        without = png(page)
        assert without != with_question
        page.evaluate("window.mountFor('skill:q2', 'q2')")                          # leave the question and come back
        page.evaluate("window.mountFor('skill:q1', 'q1')")
        page.wait_for_selector(".mx-board canvas")
        assert png(page) == without                                                 # it did not come back by itself
        page.click(".mx-board [data-do='question']")
        page.click(".mx-board [data-tool='pen']")
        assert png(page) == with_question                                           # the button places it again


def right_drag(page, x0, y0, x1, y1):
    page.mouse.move(x0, y0)
    page.mouse.down(button="right")
    page.mouse.move((x0 + x1) / 2, (y0 + y1) / 2, steps=10)
    page.mouse.move(x1, y1, steps=10)
    page.mouse.up(button="right")


def test_holding_the_right_button_erases_whatever_tool_is_chosen_and_the_tool_stays(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        page.click(".mx-board [data-tool='pen']")
        blank = png(page)                                                           # the question only
        draw_line(page)
        assert png(page) != blank
        menus = []
        page.on("popup", lambda p: menus.append(p))
        box = page.locator(".mx-board canvas").bounding_box()
        x, y = box["x"] + 60, box["y"] + 120
        right_drag(page, x - 10, y - 10, x + 130, y + 70)                           # the right button, held, over the stroke
        page.mouse.move(box["x"] + 5, box["y"] + box["height"] - 5)
        assert png(page) == blank and not menus                                     # the stroke is erased; the question stays; no context menu
        assert page.get_attribute(".mx-board", "data-tool") == "pen"                 # the pen is still the chosen tool
        draw_line(page)
        assert png(page) != blank                                                   # and the left button still draws with it


def test_the_right_button_erases_with_the_chosen_eraser_size_and_leaves_the_question_alone(browser):
    with running(create_app()) as url:
        page = board_page(browser, url, DESKTOP)
        page.click("[data-board-toggle]")
        page.wait_for_selector(".mx-board canvas")
        blank = png(page)
        draw_line(page, 300, 0)                                                     # a long horizontal stroke
        box = page.locator(".mx-board canvas").bounding_box()
        x, y = box["x"] + 60, box["y"] + 120
        page.click(".mx-board [data-tool='eraser']")
        page.click(".mx-board [data-eraser='16']")                                  # the small eraser
        page.click(".mx-board [data-tool='pen']")                                   # back to the pen: the right button still uses the small eraser
        right_drag(page, x + 100, y - 40, x + 100, y + 40)                          # a short pass across the middle only
        page.mouse.move(box["x"] + 5, box["y"] + box["height"] - 5)
        partly = png(page)
        assert partly != blank                                                      # the ends of the stroke are still there: a small eraser, not a wipe
        right_drag(page, x - 20, y, x + 320, y)
        page.mouse.move(box["x"] + 5, box["y"] + box["height"] - 5)
        assert png(page) == blank                                                   # all of it gone; the question's copy untouched
