"""Browser checks of the sketch board beside a skill's exercise (static/math-board.js).
Optional, like the other browser tests: pip install playwright && playwright install chromium."""
import re
import socket
import threading
import time

import pytest
import uvicorn

from app.main import create_app

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture(scope="module")
def server():
    app = create_app()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        srv = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=srv.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not srv.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            srv.should_exit = True
            thread.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def open_skill(browser, server, width, height):
    ctx = browser.new_context(viewport={"width": width, "height": height})
    ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    ctx.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    ctx.add_init_script("try{localStorage.setItem('mathly.sound','off')}catch{}")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server)
    playwright.expect(page.locator(".mx-trail")).to_be_visible()
    page.locator(".mx-star.st-next").click()
    playwright.expect(page.locator(".mx-sheet")).to_be_visible()
    return page, errors


def ink_pixels(page):
    return page.evaluate("""()=>{ const c=document.querySelector('.mx-board canvas'), d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
      let n=0; for(let i=3;i<d.length;i+=4) if(d[i]) n++; return n; }""")


def draw_line(page):
    box = page.locator(".mx-board canvas").bounding_box()
    x, y = box["x"] + 60, box["y"] + 60
    page.mouse.move(x, y)
    page.mouse.down()
    for k in range(1, 12):
        page.mouse.move(x + k * 15, y + k * 6)
    page.mouse.up()


def touch(page, events):
    """Sends pointer events of a finger or a pen to the board: [(type, id, x, y, kind)], x and y from its corner."""
    page.evaluate("""(events)=>{ const c=document.querySelector('.mx-board canvas'), r=c.getBoundingClientRect();
      for(const [type,id,x,y,kind] of events) c.dispatchEvent(new PointerEvent(type,{pointerId:id,pointerType:kind||'touch',
        clientX:r.left+x,clientY:r.top+y,button:type==='pointermove'?-1:0,buttons:type==='pointerup'?0:1,pressure:.5,bubbles:true,isPrimary:id===1})); }""", events)


def test_on_a_phone_the_board_opens_full_screen_over_the_exercise(browser, server):
    page, errors = open_skill(browser, server, 390, 844)
    assert page.locator(".mx-board").count() == 0   # nothing until asked
    page.locator("[data-board-toggle]").click()
    board = page.locator(".mx-board.full")
    playwright.expect(board).to_be_visible()
    box = board.bounding_box()
    assert box["width"] == 390 and box["height"] == 844
    touch(page, [("pointerdown", 1, 60, 200), *[("pointermove", 1, 60 + k * 20, 200) for k in range(1, 10)], ("pointerup", 1, 240, 200)])
    assert alpha_near(page, 150, 200) > 0   # one finger draws

    # two fingers scroll the paper and draw nothing
    touch(page, [("pointerdown", 2, 100, 500), ("pointerdown", 3, 200, 500),
                 *[e for k in range(1, 11) for e in (("pointermove", 2, 100, 500 - k * 30), ("pointermove", 3, 200, 500 - k * 30))],
                 ("pointerup", 2, 100, 200), ("pointerup", 3, 200, 200)])
    assert alpha_near(page, 150, 200) == 0 and alpha_near(page, 150, 0) == 0   # the line went up out of sight
    playwright.expect(page.locator(".mx-board-top")).to_be_visible()
    page.locator(".mx-board-top").click()
    assert alpha_near(page, 150, 200) > 0 and alpha_near(page, 150, 500) == 0

    # once a pen has written, a resting hand does not draw
    touch(page, [("pointerdown", 5, 60, 600, "pen"), ("pointermove", 5, 200, 600, "pen"), ("pointerup", 5, 200, 600, "pen")])
    touch(page, [("pointerdown", 6, 60, 700), ("pointermove", 6, 200, 700), ("pointerup", 6, 200, 700)])
    assert alpha_near(page, 130, 600) > 0 and alpha_near(page, 130, 700) == 0

    page.locator(".mx-board-back").click()   # back to the question; the sketch waits
    playwright.expect(page.locator(".mx-board")).to_have_count(0)
    playwright.expect(page.locator(".mx-sheet")).to_be_visible()
    page.locator("[data-board-toggle]").click()
    assert alpha_near(page, 150, 200) > 0
    page.keyboard.press("Escape")   # closes the board, not the exercise
    playwright.expect(page.locator(".mx-board")).to_have_count(0)
    playwright.expect(page.locator(".mx-sheet")).to_be_visible()
    assert errors == []


def test_board_turns_on_draws_undoes_and_is_remembered(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    toggle = page.locator("[data-board-toggle]")
    playwright.expect(toggle).to_be_visible()
    playwright.expect(toggle).to_have_attribute("aria-pressed", "false")
    toggle.click()
    playwright.expect(page.locator(".mx-board")).to_be_visible()
    playwright.expect(page.locator(".mx-sheet")).to_have_class(re.compile(r"\bwith-board\b"))

    # the board and the exercise sit side by side, not on top of each other
    board, sheet = page.locator(".mx-board").bounding_box(), page.locator(".mx-sheet").bounding_box()
    assert board["x"] + board["width"] <= sheet["x"]

    draw_line(page)
    assert ink_pixels(page) > 50
    page.keyboard.press("Control+z")
    assert ink_pixels(page) == 0

    draw_line(page)
    page.locator(".mx-board [data-do=clear]").click()
    assert ink_pixels(page) == 0
    page.locator(".mx-board [data-do=undo]").click()   # a clear can be undone
    assert ink_pixels(page) > 50

    # closed and opened again: the board is still on and the same question keeps its sketch
    page.locator(".mx-x").click()
    page.locator(".mx-star.st-next").click()
    playwright.expect(page.locator(".mx-board")).to_be_visible()
    assert ink_pixels(page) > 50

    page.locator(".mx-board-bar [data-do=hide]").click()
    playwright.expect(page.locator(".mx-board")).to_have_count(0)
    playwright.expect(page.locator("[data-board-toggle]")).to_have_attribute("aria-pressed", "false")
    assert page.evaluate("localStorage.getItem('mathly.board')") == "off"
    assert errors == []


def alpha_near(page, x, y):
    """The most ink in the 3x3 board pixels around (x, y), in CSS pixels from the board's corner."""
    return page.evaluate("""([x,y])=>{ const c=document.querySelector('.mx-board canvas'), d=devicePixelRatio||1;
      const px=c.getContext('2d').getImageData(Math.round(x*d)-1,Math.round(y*d)-1,3,3).data; let m=0;
      for(let i=3;i<px.length;i+=4) m=Math.max(m,px[i]); return m; }""", [x, y])


def drag(page, a, b, steps=10):
    box = page.locator(".mx-board canvas").bounding_box()
    page.mouse.move(box["x"] + a[0], box["y"] + a[1])
    page.mouse.down()
    for k in range(1, steps + 1):
        page.mouse.move(box["x"] + a[0] + (b[0] - a[0]) * k / steps, box["y"] + a[1] + (b[1] - a[1]) * k / steps)
    page.mouse.up()


def board_on(page):
    page.locator("[data-board-toggle]").click()
    playwright.expect(page.locator(".mx-board")).to_be_visible()


def test_lines_snap_circles_and_a_bigger_eraser(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)

    page.locator(".mx-board [data-tool=line]").click()
    drag(page, (100, 100), (300, 100))
    assert alpha_near(page, 200, 100) > 0
    drag(page, (305, 108), (305, 300))   # starts near the first line's end: it starts exactly there
    assert alpha_near(page, 300, 120) > 0 and alpha_near(page, 306, 120) == 0

    page.locator(".mx-board [data-tool=circle]").click()
    drag(page, (450, 300), (530, 300))   # from the center out to the radius
    assert alpha_near(page, 450, 380) > 0 and alpha_near(page, 450, 300) == 0

    # the eraser's sizes show only with the eraser; the big one wipes what the small one misses
    playwright.expect(page.locator(".mx-board-sizes")).to_be_hidden()
    page.locator(".mx-board [data-tool=eraser]").click()
    playwright.expect(page.locator(".mx-board-sizes")).to_be_visible()
    page.locator(".mx-board [data-eraser='16']").click()
    drag(page, (150, 125), (250, 125))
    assert alpha_near(page, 200, 100) > 0
    page.locator(".mx-board [data-eraser='90']").click()
    drag(page, (150, 125), (250, 125))
    assert alpha_near(page, 200, 100) == 0
    assert errors == []


def test_the_practice_exam_has_a_board_with_a_sketch_per_question(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    page.locator(".mx-x").click()
    page.locator(".mx-quiz-card").click()
    page.locator("[data-act=quiz-start]").click()
    playwright.expect(page.locator(".mx-quiz-sheet")).to_be_visible()
    board_on(page)
    draw_line(page)
    assert ink_pixels(page) > 50
    page.locator("[data-act=quiz-next]").click()
    playwright.expect(page.locator(".mx-board")).to_be_visible()   # still on for the next question, on a clean page
    assert ink_pixels(page) == 0
    page.locator("[data-act=quiz-prev]").click()
    assert ink_pixels(page) > 50
    assert errors == []


def test_elements_move_together_when_joined_and_can_be_deleted(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    page.locator(".mx-board [data-tool=line]").click()
    drag(page, (100, 300), (300, 300))
    drag(page, (302, 302), (200, 150))   # snaps to the first line's end
    drag(page, (198, 148), (102, 298))   # and closes the triangle
    page.locator(".mx-board [data-tool=circle]").click()
    drag(page, (500, 250), (550, 250))

    page.locator(".mx-board [data-tool=move]").click()
    drag(page, (200, 300), (200, 400))   # grab the base: the whole triangle moves
    assert alpha_near(page, 200, 300) == 0 and alpha_near(page, 200, 400) > 0
    assert alpha_near(page, 200, 250) > 0   # the top corner came along (was at 150)
    assert alpha_near(page, 550, 250) > 0   # the circle stayed

    drag(page, (550, 250), (550, 450))   # the circle alone
    assert alpha_near(page, 550, 250) == 0 and alpha_near(page, 550, 450) > 0
    playwright.expect(page.locator(".mx-board-del")).to_be_visible()
    page.keyboard.press("Delete")
    assert alpha_near(page, 550, 450) == 0
    page.keyboard.press("Control+z")   # a delete can be undone, and so can a move
    assert alpha_near(page, 550, 450) > 0
    page.keyboard.press("Control+z")
    assert alpha_near(page, 550, 250) > 0
    assert errors == []


def test_the_eraser_cuts_a_pen_stroke_and_a_moved_shape_comes_whole(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    drag(page, (100, 200), (500, 200), steps=30)   # a pen stroke
    page.locator(".mx-board [data-tool=eraser]").click()
    page.locator(".mx-board [data-eraser='40']").click()
    drag(page, (300, 150), (300, 250))   # cut through the middle
    assert alpha_near(page, 300, 200) == 0
    assert alpha_near(page, 150, 200) > 0 and alpha_near(page, 450, 200) > 0

    page.locator(".mx-board [data-tool=move]").click()
    drag(page, (150, 200), (150, 400))   # the left piece is an element of its own
    assert alpha_near(page, 150, 400) > 0 and alpha_near(page, 450, 200) > 0
    assert errors == []


def test_the_question_is_copied_to_the_top_of_the_board(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    width = page.locator(".mx-board canvas").bounding_box()["width"]
    assert alpha_near(page, width - 40, 30) == 0
    page.locator(".mx-board [data-do=question]").click()
    assert alpha_near(page, width - 40, 30) > 0   # a card at the top
    playwright.expect(page.locator(".mx-board [data-tool=move]")).to_have_attribute("aria-pressed", "true")
    drag(page, (width - 40, 30), (width - 40, 430))   # it moves like anything else
    assert alpha_near(page, width - 40, 30) == 0 and alpha_near(page, width - 40, 430) > 0
    page.locator(".mx-board-del").click()
    assert ink_pixels(page) == 0
    assert errors == []


def test_the_wheel_scrolls_an_endless_paper(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    drag(page, (100, 100), (300, 100))
    box = page.locator(".mx-board canvas").bounding_box()
    page.mouse.move(box["x"] + 300, box["y"] + 300)
    page.mouse.wheel(0, -500)   # never above the top
    page.wait_for_timeout(100)
    assert alpha_near(page, 200, 100) > 0
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(100)
    assert alpha_near(page, 200, 100) == 0   # scrolled out of sight
    playwright.expect(page.locator(".mx-board-top")).to_be_visible()
    drag(page, (100, 300), (300, 300))   # drawn far down the paper
    page.locator(".mx-board-top").click()
    assert alpha_near(page, 200, 100) > 0 and alpha_near(page, 200, 300) == 0
    page.mouse.move(box["x"] + 300, box["y"] + 300)
    page.mouse.wheel(0, 2000)
    page.wait_for_timeout(100)
    assert alpha_near(page, 200, 300) > 0
    playwright.expect(page.locator(".mx-board-send")).to_be_hidden()   # handing in is the unit quiz's
    assert errors == []


def type_math(page, at, latex):
    """Taps the board with the math tool at `at`, types `latex` into the math field and adds it."""
    box = page.locator(".mx-board canvas").bounding_box()
    page.mouse.click(box["x"] + at[0], box["y"] + at[1])
    field = page.locator(".mx-board-mathedit math-field")
    playwright.expect(field).to_be_visible(timeout=10000)
    page.evaluate("v=>{document.querySelector('.mx-board-mathedit math-field').value=v}", latex)
    page.locator(".mx-board-mathedit [data-math=ok]").dispatch_event("pointerdown")
    playwright.expect(page.locator(".mx-board-mathedit")).to_have_count(0)


def test_typed_math_is_an_element_like_any_other(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    page.locator(".mx-board [data-tool=math]").click()
    box = page.locator(".mx-board canvas").bounding_box()
    page.mouse.click(box["x"] + 100, box["y"] + 200)
    playwright.expect(page.locator(".mx-board-mathedit math-field")).to_be_visible(timeout=10000)
    assert page.evaluate("window.mathVirtualKeyboard.visible")   # the math keyboard opens with it
    page.keyboard.press("Escape")   # cancels the formula, not the board
    playwright.expect(page.locator(".mx-board-mathedit")).to_have_count(0)
    playwright.expect(page.locator(".mx-board")).to_be_visible()
    assert ink_pixels(page) == 0

    type_math(page, (100, 200), r"\frac{x^2-9}{x+3}=x-3")
    assert ink_pixels(page) > 100
    assert alpha_near(page, 112, 200) > 0 or alpha_near(page, 130, 200) > 0

    type_math(page, (100, 200), r"x^2")   # tapping it with the math tool edits it, in place
    assert ink_pixels(page) > 0
    page.locator(".mx-board [data-do=undo]").click()   # back to the fraction

    page.locator(".mx-board [data-tool=move]").click()
    drag(page, (120, 200), (120, 450))
    assert alpha_near(page, 112, 200) + alpha_near(page, 130, 200) == 0
    assert alpha_near(page, 112, 450) + alpha_near(page, 130, 450) > 0   # it went with the drag, whole

    page.locator(".mx-board [data-tool=eraser]").click()
    drag(page, (100, 440), (260, 460))
    assert ink_pixels(page) == 0   # the eraser takes the whole formula
    assert errors == []


def test_the_math_renderer_draws_what_the_keyboard_makes(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    sizes = page.evaluate("""()=>[
      'x^2-5x+6=0', 'x_{1,2}=\\\\frac{-b\\\\pm\\\\sqrt{b^2-4ac}}{2a}', '\\\\sqrt[3]{8}', '\\\\left(\\\\frac{a}{b}\\\\right)^{3}',
      '\\\\left|x-2\\\\right|\\\\le 5', '\\\\angle ABC=30^{\\\\circ}', '\\\\triangle ABC\\\\cong\\\\triangle DEF', 'a\\\\perp b\\\\parallel c',
      '\\\\text{שטח}=\\\\pi r^2', '\\\\placeholder{}+1', '\\\\unknowncommand{x}', ''
    ].map(l=>{ const L=window.MathlyBoardMath.layout(l,26); return [L.w,L.a,L.d]; })""")
    assert all(w >= 0 and a >= 0 and d >= 0 for w, a, d in sizes)
    assert all(w > 10 for w, _, _ in sizes[:-1])
    frac, plain = sizes[1], sizes[0]
    assert frac[0] > plain[0] and frac[1] > plain[1]   # a fraction is wider and taller than a line of text
    assert errors == []


def test_the_move_tool_scrolls_when_it_drags_empty_paper(browser, server):
    page, errors = open_skill(browser, server, 390, 844)
    page.locator("[data-board-toggle]").click()
    touch(page, [("pointerdown", 1, 60, 300), *[("pointermove", 1, 60 + k * 20, 300) for k in range(1, 10)], ("pointerup", 1, 240, 300)])
    page.locator(".mx-board [data-tool=move]").click()
    # one finger on empty paper: the paper scrolls, the line goes up with it
    touch(page, [("pointerdown", 2, 150, 600), *[("pointermove", 2, 150, 600 - k * 20) for k in range(1, 11)], ("pointerup", 2, 150, 400)])
    assert alpha_near(page, 150, 300) == 0 and alpha_near(page, 150, 100) > 0
    playwright.expect(page.locator(".mx-board-top")).to_be_visible()
    # one finger on the line: the line moves, the paper stays
    touch(page, [("pointerdown", 3, 150, 100), *[("pointermove", 3, 150, 100 + k * 20) for k in range(1, 11)], ("pointerup", 3, 150, 300)])
    assert alpha_near(page, 150, 100) == 0 and alpha_near(page, 150, 300) > 0
    playwright.expect(page.locator(".mx-board-del")).to_be_visible()   # it is selected, not the paper scrolled
    # never above the top
    touch(page, [("pointerdown", 4, 300, 200), *[("pointermove", 4, 300, 200 + k * 60) for k in range(1, 11)], ("pointerup", 4, 300, 800)])
    playwright.expect(page.locator(".mx-board-top")).to_be_hidden()
    assert errors == []


def test_an_angle_gets_an_arc_and_its_words_at_a_triangles_corner(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    page.locator(".mx-board [data-tool=line]").click()
    drag(page, (100, 300), (300, 300))
    drag(page, (302, 302), (200, 150))
    drag(page, (198, 148), (102, 298))
    page.locator(".mx-board [data-tool=angle]").click()
    box = page.locator(".mx-board canvas").bounding_box()
    at = lambda x, y: (box["x"] + x, box["y"] + y)

    # the bottom-left corner: its edges go right (0°) and up to the top (-56°), so the arc is at radius 30, around -28°
    arc, words = (126, 286), (138, 280)
    ink_by = lambda x, y: max(alpha_near(page, x + dx, y + dy) for dx in (-6, -3, 0, 3, 6) for dy in (-4, 0, 4))
    assert alpha_near(page, *arc) == 0
    page.mouse.move(*at(112, 294))   # pointing into the corner: its arc shows, dashed, before anything is added
    assert alpha_near(page, *arc) > 0
    page.mouse.move(*at(400, 500))   # away from every corner: nothing
    assert alpha_near(page, *arc) == 0

    page.mouse.click(*at(112, 294))
    field = page.locator(".mx-board-anglein")
    playwright.expect(field).to_be_focused()
    field.fill("60")
    field.press("Enter")
    playwright.expect(field).to_have_count(0)
    assert alpha_near(page, *arc) > 0 and ink_by(*words) > 0

    # the words open again for a change; a number is shown without its degree sign, which comes back by itself
    page.mouse.click(*at(*words))
    playwright.expect(field).to_have_value("60")
    field.press("Escape")   # leaves it as it was, and the board open
    playwright.expect(field).to_have_count(0)
    playwright.expect(page.locator(".mx-board")).to_be_visible()
    assert ink_by(*words) > 0

    # the angle belongs to its corner: it moves with the triangle and goes with an undo
    page.locator(".mx-board [data-tool=move]").click()
    drag(page, (200, 300), (200, 400))
    assert alpha_near(page, *arc) == 0 and alpha_near(page, arc[0], arc[1] + 100) > 0
    page.keyboard.press("Control+z")   # the move
    page.keyboard.press("Control+z")   # the angle
    assert alpha_near(page, *arc) == 0 and alpha_near(page, 200, 300) > 0

    # a corner where nothing meets is no angle; Escape on a new one takes it back
    page.locator(".mx-board [data-tool=angle]").click()
    page.mouse.click(*at(500, 500))
    playwright.expect(field).to_have_count(0)
    page.mouse.click(*at(112, 294))
    field.press("Escape")
    assert alpha_near(page, *arc) == 0

    # α, β and γ are a tap away, typed where the cursor is; a number added to them is in degrees too
    page.mouse.click(*at(112, 294))
    page.locator(".mx-board-angleedit button", has_text="β").click()
    playwright.expect(field).to_have_value("β")
    playwright.expect(field).to_be_focused()
    page.keyboard.type("+90")
    page.keyboard.press("Enter")
    playwright.expect(field).to_have_count(0)
    assert alpha_near(page, *arc) > 0 and ink_by(*words) > 0
    page.mouse.click(*at(*words))
    playwright.expect(field).to_have_value("β+90")   # its degree sign comes back by itself
    field.fill("180-alpha")   # the letters' names become the letters
    field.press("Enter")
    page.mouse.click(*at(*words))
    playwright.expect(field).to_have_value("180-α")

    # a double arc (equal angles are marked alike): a second arc 4 px outside the first, kept, and undone like the rest
    outer = (100 + 34 * 0.883, 300 - 34 * 0.469)
    assert alpha_near(page, *outer) == 0
    page.locator(".mx-board-arcs [data-arcs='2']").click()
    assert alpha_near(page, *outer) > 0   # shown at once
    field.press("Enter")
    assert alpha_near(page, *arc) > 0 and alpha_near(page, *outer) > 0
    page.mouse.click(*at(112, 294))
    playwright.expect(page.locator(".mx-board-arcs [data-arcs='2']")).to_have_attribute("aria-pressed", "true")
    field.press("Escape")
    page.keyboard.press("Control+z")
    assert alpha_near(page, *arc) > 0 and alpha_near(page, *outer) == 0

    # its colour, arcs and words together, picked in the same box
    red = lambda: page.evaluate("""([x,y])=>{ const c=document.querySelector('.mx-board canvas'), d=devicePixelRatio||1;
      const px=c.getContext('2d').getImageData(Math.round(x*d)-1,Math.round(y*d)-1,3,3).data; let n=0;
      for(let i=0;i<px.length;i+=4) if(px[i+3]>128&&px[i]>150&&px[i+2]<130) n++; return n; }""", list(arc))
    assert red() == 0
    page.mouse.click(*at(112, 294))
    page.locator(".mx-board-colors [data-color='#D3455B']").click()
    assert red() > 0   # shown at once
    field.press("Enter")
    assert red() > 0
    page.keyboard.press("Control+z")
    assert red() == 0
    assert errors == []


def test_angles_where_a_line_meets_a_side_or_crosses_another(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    page.locator(".mx-board [data-tool=line]").click()
    drag(page, (90, 438), (420, 438))
    drag(page, (92, 436), (200, 80))
    drag(page, (202, 82), (418, 436))
    drag(page, (200, 82), (262, 433))   # from the top down to the base, ending a little short: it snaps onto the base
    drag(page, (120, 300), (380, 300))   # across the triangle
    page.locator(".mx-board [data-tool=angle]").click()
    box = page.locator(".mx-board canvas").bounding_box()
    field = page.locator(".mx-board-anglein")

    def add(x, y, text):
        page.mouse.click(box["x"] + x, box["y"] + y)
        playwright.expect(field).to_be_focused()
        field.fill(text)
        field.press("Enter")

    foot = 262 + (438 - 433) * 62 / 353   # where the middle line meets the base
    assert alpha_near(page, foot, 437) > 0 and alpha_near(page, foot, 441) == 0   # it reached the base, not past it
    add(250, 430, "α")   # either side of the line drawn from the base
    add(275, 430, "β")
    assert alpha_near(page, foot - 30, 438 - 3) > 0 and alpha_near(page, foot + 30, 438 - 3) > 0
    add(191, 106, "x")   # the two halves of the top corner
    add(211, 104, "y")
    add(205, 105, "2α+β")   # pointing along the middle line: the whole top angle, a wider arc
    assert page.locator(".mx-board-anglein").count() == 0
    # a narrow half's words sit right by its arc (radius 30), not far down between the lines; the whole angle's arc
    # goes around them
    x_words = (200 + 45 * -0.07, 80 + 45 * 1.0)
    assert max(alpha_near(page, x_words[0] + dx, x_words[1] + dy) for dx in (-4, 0, 4) for dy in (-4, 0, 4)) > 0
    add(250, 306, "60")   # where two lines cross
    # it all moves as one: the line from the base and the crossing line come with the triangle, their angles too
    page.locator(".mx-board [data-tool=move]").click()
    drag(page, (150, 438), (150, 538))
    assert alpha_near(page, foot - 30, 535) > 0 and alpha_near(page, foot - 30, 435) == 0
    assert alpha_near(page, 300, 400) > 0   # the crossing line, 100 lower
    assert errors == []


def test_a_right_angle_is_marked_with_a_square(browser, server):
    page, errors = open_skill(browser, server, 1440, 900)
    board_on(page)
    page.locator(".mx-board [data-tool=line]").click()
    drag(page, (100, 400), (340, 400))
    drag(page, (102, 398), (100, 160))
    drag(page, (100, 162), (338, 398))
    page.locator(".mx-board [data-tool=angle]").click()
    box = page.locator(".mx-board canvas").bounding_box()
    page.mouse.click(box["x"] + 112, box["y"] + 388)
    page.locator(".mx-board-arcs [data-arcs='right']").click()
    page.locator(".mx-board-anglein").press("Enter")
    # a square of side 14 in the corner: its far corner at (114, 386), and no arc at radius 30
    assert alpha_near(page, 114, 386) > 0 and alpha_near(page, 107, 386) > 0 and alpha_near(page, 114, 393) > 0
    assert alpha_near(page, 100 + 30 * 0.707, 400 - 30 * 0.707) == 0
    page.mouse.click(box["x"] + 112, box["y"] + 388)   # the square opens it again, as an arc does
    playwright.expect(page.locator(".mx-board-arcs [data-arcs='right']")).to_have_attribute("aria-pressed", "true")
    page.locator(".mx-board-arcs [data-arcs='1']").click()
    page.locator(".mx-board-anglein").press("Enter")
    assert alpha_near(page, 114, 386) == 0 and alpha_near(page, 100 + 30 * 0.707, 400 - 30 * 0.707) > 0
    assert errors == []


def test_the_board_has_a_scientific_calculator(browser, server):
    page, errors = open_skill(browser, server, 1400, 900)
    page.locator("[data-board-toggle]").click()
    page.locator('.mx-board [data-do="calc"]').click()
    calc = page.locator(".mx-calc")
    playwright.expect(calc).to_be_visible()

    def tap(*labels):
        for label in labels:
            calc.locator("button", has=page.locator(f"b:text-is('{label}')")).first.click()

    tap("sin", "3", "0", ")", "=")
    playwright.expect(calc.locator("output")).to_have_text("0.5")
    tap("S⇔D")
    playwright.expect(calc.locator("output")).to_have_text("1/2")
    tap("×", "4", "=")   # carries on from the answer
    playwright.expect(calc.locator("output")).to_have_text("2")
    tap("AC", "SHIFT", "sin", "1", ")", "=")   # sin⁻¹(1) in degrees
    playwright.expect(calc.locator("output")).to_have_text("90")
    tap("AC", "2", "÷", "0", "=")
    playwright.expect(calc.locator("output")).to_have_text("שגיאה")
    assert not errors
