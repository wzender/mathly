"""Browser checks of the night sky (static/math-sky.js): stars, gold, fading, the streak and comets.
Optional, like the other browser tests: pip install playwright && playwright install chromium."""
import json
import socket
import threading
import time
from datetime import date, datetime, timedelta, timezone

import pytest
import uvicorn

from app.main import create_app

playwright = pytest.importorskip("playwright.sync_api")
KEY = "mathly.progress.v1:guest"


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


def page_with(browser, server, progress=None, no_chance=False):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    if no_chance:   # no comet by chance: only the sure ones come
        ctx.add_init_script("Math.random=()=>0.99")
    ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    ctx.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    ctx.add_init_script("try{localStorage.setItem('mathly.sound','off')}catch{}")
    if progress is not None:
        ctx.add_init_script(f"localStorage.setItem({json.dumps(KEY)},{json.dumps(json.dumps(progress))})")
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server)
    playwright.expect(page.locator(".mx-greet")).to_be_visible()
    return page, errors


def progress_of(page):
    return page.evaluate(f"JSON.parse(localStorage.getItem({json.dumps(KEY)})||'{{}}')")


def answer_skill_right(page):
    """Answers the open skill's questions right at the first try, until a celebration shows."""
    for _ in range(20):
        if page.locator(".sky-cele").count():
            return
        page.locator(".mx-choices button[data-right]").first.click()
        page.wait_for_timeout(150)
        if page.locator(".sky-cele").count():
            return
        page.locator(".mx-ok button[data-id]").first.click()
    raise AssertionError("no celebration")


def test_clean_run_turns_the_next_star_gold(browser, server):
    page, errors = page_with(browser, server)
    playwright.expect(page.locator(".mx-task.hero small")).to_have_text("הכוכב הבא")
    nxt = page.locator(".mx-task.hero").get_attribute("data-id")
    page.locator(".mx-task.hero").click()
    answer_skill_right(page)
    playwright.expect(page.locator(".sky-cele h2").first).to_have_text("כוכב זהב!")
    while page.locator(".sky-cele [data-sky=go]").count():
        page.locator(".sky-cele [data-sky=go]").first.click()
    p = progress_of(page)
    assert p["done"][nxt] and p["gold"][nxt]
    assert p["days"][date.today().isoformat()] >= 5
    page.locator(".mx-x").click()
    page.locator('.mx-nav [data-view="path"]').click()
    playwright.expect(page.locator(f'.mx-star[data-id="{nxt}"]')).to_have_class("mx-node mx-star st-gold")
    playwright.expect(page.locator(".sky-chip.flame b")).to_have_text("1")   # today's goal is met
    assert not errors


def test_a_faded_star_comes_first_and_one_answer_brightens_it(browser, server):
    old = (datetime.now(timezone.utc) - timedelta(days=20)).isoformat()
    page, errors = page_with(browser, server, {"done": {"t_ext": old}, "seen": {"t_ext": old}, "solved": {"t_ext": list(range(10))}})
    task = page.locator(".mx-task", has_text="להאיר כוכב דועך")
    playwright.expect(task).to_have_attribute("data-id", "t_ext")
    page.locator('.mx-nav [data-view="path"]').click()
    playwright.expect(page.locator('.mx-star[data-id="t_ext"]')).to_have_class("mx-node mx-star st-fading")
    page.locator('.mx-star[data-id="t_ext"]').click()
    page.locator(".mx-choices button[data-right]").first.click()
    playwright.expect(page.locator(".sky-toast", has_text="זורח שוב")).to_be_visible()
    page.locator(".mx-x").click()
    playwright.expect(page.locator('.mx-star[data-id="t_ext"]')).to_have_class("mx-node mx-star st-lit")
    assert not errors


def test_streak_forgives_one_missed_day_not_two(browser, server):
    day = lambda n: (date.today() - timedelta(days=n)).isoformat()
    page, _ = page_with(browser, server, {"days": {day(1): 5, day(3): 6, day(4): 5, day(7): 5}})
    playwright.expect(page.locator(".sky-chip.flame b")).to_have_text("3")   # 1, 3, 4; days 5 and 6 both missed
    playwright.expect(page.locator(".mx-week .on")).to_have_count(3)


def test_a_caught_comet_joins_the_collection(browser, server):
    page, errors = page_with(browser, server, no_chance=True)
    page.locator(".mx-task.hero").click()
    answer_skill_right(page)                                 # the first gold star of all brings a comet
    while page.locator(".sky-cele [data-sky=go]").count():
        page.locator(".sky-cele [data-sky=go]").first.click()
    comet = page.locator(".sky-comet")
    playwright.expect(comet).to_have_count(1, timeout=3000)
    comet.dispatch_event("click")                            # it never stands still for a normal click
    playwright.expect(page.locator(".sky-cele h2")).to_have_text("תפסתם שביט נדיר!")
    page.locator(".sky-cele [data-sky=go]").click()
    assert len(progress_of(page)["comets"]) == 1
    page.locator(".mx-x").click()
    page.locator('.mx-nav [data-view="sky"]').click()
    playwright.expect(page.locator(".mx-comet.have")).to_have_count(1)
    assert not errors
