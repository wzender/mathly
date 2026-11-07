"""The prompter's slide mode (static/prompter.js): a slide script shown one slide at a time, sized for a mini iPad."""
import pathlib

import pytest

playwright = pytest.importorskip("playwright.sync_api")

JS = (pathlib.Path(__file__).parent.parent / "static" / "prompter.js").read_text()
SCRIPT = """Part 1 — Opening
Slide 1 — From Data to Decisions
Opening · 35 seconds
Good morning, everyone.
Today is about *data*. [CLICK]
Slide 2 — Why This Matters
1 minute
Before the tools, the why. // Then the questions.
Slide 3 — Thank You
15 seconds
Thank you."""


def opened(p, text, size=(744, 1133)):
    page = p.chromium.launch().new_page(viewport={"width": size[0], "height": size[1]})
    page.set_content("<html><body></body></html>")
    page.add_script_tag(content=JS)
    page.evaluate("t=>window.MathlyPrompter.open(t)", text)
    return page


def test_reads_a_slide_script():
    with playwright.sync_playwright() as p:
        page = opened(p, SCRIPT)
        slides = page.evaluate("t=>window.MathlyPrompter.parse(t).slides", SCRIPT)
        assert [(s["num"], s["title"], s["secs"], s["label"]) for s in slides] == [
            (1, "From Data to Decisions", 35, "Opening"), (2, "Why This Matters", 60, ""), (3, "Thank You", 15, "")]
        assert slides[0]["part"] == "Part 1 — Opening"
        assert page.evaluate("t=>window.MathlyPrompter.parse(t).slides", "Just a text\nwith Slide 3 in it") is None


def test_one_slide_at_a_time_with_a_clock():
    with playwright.sync_playwright() as p:
        page = opened(p, SCRIPT)
        root = page.locator(".mxp")
        playwright.expect(root).to_have_class("mxp slides")
        playwright.expect(page.locator(".mxp-snum")).to_have_text("1 / 3")
        playwright.expect(page.locator(".mxp-stitle")).to_contain_text("From Data to Decisions")
        playwright.expect(page.locator(".mxp-sbody")).not_to_contain_text("35 seconds")    # the timing is not read out
        playwright.expect(page.locator(".mxp-sbody em")).to_have_text("data")              # *data* is stressed
        playwright.expect(page.locator(".mxp-sbody .mxp-cue")).to_have_text("CLICK ⏵")
        playwright.expect(page.locator(".mxp-timer")).to_have_text("0:00 / 0:35")
        playwright.expect(page.locator(".mxp-sfoot")).to_contain_text("Why This Matters")   # the next slide
        page.locator(".mxp-sbody").click()                                  # the first tap starts the clock, stays put
        playwright.expect(root).to_have_class("mxp slides playing")
        playwright.expect(page.locator(".mxp-snum")).to_have_text("1 / 3")
        page.keyboard.press("PageDown")                                     # a clicker: the next slide
        playwright.expect(page.locator(".mxp-snum")).to_have_text("2 / 3")
        playwright.expect(page.locator(".mxp-sbody .mxp-cue.pause")).to_have_count(1)
        playwright.expect(page.locator(".mxp-delta")).to_contain_text("לפני הזמן")          # 35s planned, ~0s used
        page.keyboard.press("PageUp")
        playwright.expect(page.locator(".mxp-snum")).to_have_text("1 / 3")
        page.keyboard.press("s")                                            # S: scrolling, headings shown dimmed
        playwright.expect(root).to_have_class("mxp")
        playwright.expect(page.locator(".mxp-text .mxp-dir")).to_have_count(7)
        playwright.expect(page.locator(".mxp-text")).to_have_text(SCRIPT)
        page.keyboard.press("s")
        playwright.expect(root).to_have_class("mxp slides playing")


def test_swipes_on_a_tablet():
    with playwright.sync_playwright() as p:
        page = opened(p, SCRIPT)
        page.locator(".mxp-sbody").click()                                  # start the clock

        def swipe(dx):
            box = page.locator(".mxp-sbody").bounding_box()
            x, y = box["x"] + box["width"] / 2, box["y"] + 100
            page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + dx, y, steps=5); page.mouse.up()
        swipe(-200)
        playwright.expect(page.locator(".mxp-snum")).to_have_text("2 / 3")
        swipe(200)
        playwright.expect(page.locator(".mxp-snum")).to_have_text("1 / 3")


def test_long_notes_shrink_to_fit():
    long = "Slide 1 — Long\n40 seconds\n" + "\n".join(["A fairly long sentence that the speaker reads out loud."] * 10) \
        + "\nSlide 2 — End\nBye."
    with playwright.sync_playwright() as p:
        page = opened(p, long)
        size = page.locator(".mxp-sbody").evaluate("e=>parseFloat(e.style.fontSize)")
        assert 25 <= size < 34
        assert page.locator(".mxp-sbody").evaluate("e=>e.scrollHeight<=e.clientHeight+4")
        playwright.expect(page.locator(".mxp-more")).to_be_hidden()
