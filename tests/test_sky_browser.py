"""Browser checks of the night sky (static/math-sky.js): stars, gold, fading, the streak and comets.
Optional, like the other browser tests: pip install playwright && playwright install chromium."""
import json
import re
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


def page_with(browser, server, progress=None, no_chance=False, now=None):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    if no_chance:   # no comet by chance: only the sure ones come
        ctx.add_init_script("Math.random=()=>0.99")
    ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    ctx.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    ctx.add_init_script("try{localStorage.setItem('mathly.sound','off')}catch{}")
    if progress is not None:
        ctx.add_init_script(f"localStorage.setItem({json.dumps(KEY)},{json.dumps(json.dumps(progress))})")
    page = ctx.new_page()
    if now:   # the date the page sees; timers run as usual
        page.clock.set_fixed_time(now)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server)
    page.locator('.mx-nav [data-view="path"]').click()   # the app opens on home; the trail is on the path tab
    playwright.expect(page.locator(".mx-trail")).to_be_visible()
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
    nxt = page.locator(".mx-star.st-next").get_attribute("data-id")
    page.locator(".mx-star.st-next").click()
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
    page.locator(".mx-hud .sky-chip.flame").click()                     # the streak calendar
    sheet = page.locator(".mx-streak-sheet")
    playwright.expect(sheet.locator(".mx-shero b")).to_have_text("3")
    playwright.expect(sheet.locator(".mx-sstats b").first).to_have_text("3")   # the longest streak
    met = saved = 0
    for _ in range(2):   # the last week can start in the month before
        met += sheet.locator(".mx-cday.s-met").count()
        saved += sheet.locator(".mx-cday.s-saved").count()
        prev = sheet.locator("[data-act=cal-prev]")
        if prev.is_disabled():
            break
        prev.click()
    assert (met, saved) == (4, 1)   # day 2 is forgiven; days 5 and 6 are not


def test_a_caught_comet_joins_the_collection(browser, server):
    page, errors = page_with(browser, server, no_chance=True)
    page.locator(".mx-star.st-next").click()
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


def test_home_shows_the_tally_on_top_and_opens_at_the_next_skill(browser, server):
    done = {i: "2026-01-01T00:00:00+00:00" for i in ["t_ext"]}
    page, errors = page_with(browser, server, {"done": done, "solved": {"t_ext": list(range(10))}})
    playwright.expect(page.locator(".mx-hud .sky-chip.stars b")).to_have_text("1")
    playwright.expect(page.locator(".mx-hud .sky-chip.flame")).to_be_visible()
    playwright.expect(page.locator(".mx-nav button")).to_have_count(3)   # home, path, collection
    nxt = page.locator(".mx-star.st-next")
    playwright.expect(nxt).to_be_in_viewport()
    page.evaluate("document.getElementById('mathView').scrollTo(0, 99999)")   # the tally stays on top while scrolling
    playwright.expect(page.locator(".mx-hud")).to_be_in_viewport()
    page.locator(".mx-daily").click()
    playwright.expect(page.locator(".mx-streak-sheet .mx-cday.today")).to_have_count(1)
    assert not errors


def test_a_mistake_is_quiet_hides_the_answer_and_needs_a_clean_run_to_finish(browser, server):
    page, errors = page_with(browser, server, no_chance=True)
    page.locator('.mx-star[data-id="t_ext"]').click()
    for _ in range(9):   # questions 1-9 right
        page.locator(".mx-choices button[data-right]").first.click()
        page.locator(".mx-ok button[data-id]").first.click()
    page.locator(".mx-choices button:not([data-right])").first.click()   # question 10 wrong
    playwright.expect(page.locator(".mx-bad")).to_be_visible()
    assert page.locator(".mx-choices button.right").count() == 0         # the right answer is not revealed
    assert page.locator(".mx-choices button:not([disabled])").count() == 0
    slips = progress_of(page)["slips"]
    assert [(s["id"], s["via"]) for s in slips] == [("t_ext", "practice")] and slips[0]["m"]   # the mistake is remembered
    page.locator(".mx-bad button[data-id=t_ext]").first.click()
    page.locator(".mx-choices button[data-right]").first.click()         # it comes back and is solved
    playwright.expect(page.locator(".mx-ok b")).to_have_text(re.compile("תיקנתם|הטעות מקודם"))   # fixing is praised
    playwright.expect(page.locator(".mx-ok")).to_contain_text("עוד 2 תשובות נכונות ברצף")
    assert not progress_of(page)["done"].get("t_ext")                   # all solved, but not yet a clean run
    for _ in range(2):
        page.locator(".mx-ok button[data-id]").first.click()
        page.locator(".mx-choices button[data-right]").first.click()
    playwright.expect(page.locator(".sky-cele h2").first).to_have_text("כוכב חדש!")
    p = progress_of(page)
    assert p["done"]["t_ext"] and not p["gold"].get("t_ext")
    assert p["review"]["t_ext"]["box"] == 0                              # the first review is tomorrow
    assert not errors


def test_a_due_skill_comes_back_in_a_mixed_review(browser, server):
    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    later = (date.today() + timedelta(days=3)).isoformat()
    progress = {"done": {"t_ext": old, "t_simplify": old, "k_def": old}, "seen": {"t_ext": old, "t_simplify": old, "k_def": old},
                "review": {"t_ext": {"box": 1, "due": yesterday}, "t_simplify": {"box": 0, "due": later}}}
    page, errors = page_with(browser, server, progress, no_chance=True)
    card = page.locator(".mx-review")
    playwright.expect(card).to_contain_text("2 מיומנויות")              # t_ext is due, k_def is old; t_simplify is not yet
    card.click()
    sheet = page.locator(".mx-review-sheet")
    playwright.expect(sheet.locator("h3")).to_have_text("שאלה 1 מתוך 2")
    sheet.locator(".mx-choices button[data-right]").first.click()
    playwright.expect(sheet.locator(".mx-ok")).to_contain_text("הנושא:")
    sheet.locator("[data-act=review-next]").click()
    sheet.locator(".mx-choices button:not([data-right])").first.click()
    playwright.expect(sheet.locator(".mx-bad")).to_contain_text("יחזור מחר")
    sheet.locator("[data-act=review-next]").click()
    playwright.expect(sheet.locator(".mx-ok b")).to_have_text("החזרה הסתיימה")
    p = progress_of(page)
    boxes = sorted(p["review"][i]["box"] for i in ("t_ext", "k_def"))
    assert boxes in ([0, 0], [0, 2])                                     # the right one moved on, the wrong one starts over
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert tomorrow in {p["review"][i]["due"] for i in ("t_ext", "k_def")}
    page.locator(".mx-x").click()
    playwright.expect(page.locator(".mx-review")).to_have_count(0)      # nothing is due any more today
    assert not errors


def test_a_round_asks_ten_of_thirty_and_a_finished_skill_gets_a_new_round(browser, server):
    page, errors = page_with(browser, server, no_chance=True)
    page.locator('.mx-star[data-id="t_ext"]').click()
    playwright.expect(page.locator(".mx-qprog span").first).to_have_text("שאלה 1 מתוך 10")
    page.locator(".mx-choices button[data-right]").first.click()
    rnd = progress_of(page)["set"]["t_ext"]
    assert len(rnd) == len(set(rnd)) == 10 and all(0 <= i < 30 for i in rnd)
    page.locator(".mx-ok button[data-id]").first.click()
    for _ in range(9):
        page.locator(".mx-choices button[data-right]").first.click()
        if page.locator(".sky-cele").count():
            break
        page.locator(".mx-ok button[data-id]").first.click()
    while page.locator(".sky-cele [data-sky=go]").count():
        page.locator(".sky-cele [data-sky=go]").first.click()
    p = progress_of(page)
    assert p["done"]["t_ext"] and sorted(p["solved"]["t_ext"]) == sorted(rnd)
    page.locator(".mx-x").click()
    page.locator('.mx-star[data-id="t_ext"]').click()   # practising it again: the questions not met yet come first
    page.locator(".mx-choices button[data-right]").first.click()
    again = progress_of(page)["set"]["t_ext"]
    assert not set(again) & set(rnd)
    assert not errors


def test_progress_from_before_rounds_stays_on_the_first_ten(browser, server):
    page, errors = page_with(browser, server, {"solved": {"t_ext": [0, 1, 2]}, "at": {"t_ext": 3}})
    page.locator('.mx-star[data-id="t_ext"]').click()
    playwright.expect(page.locator(".mx-qprog span").first).to_have_text("שאלה 4 מתוך 10")
    playwright.expect(page.locator(".mx-qdots i.ok")).to_have_count(3)
    assert not errors


def test_answers_saved_by_a_page_from_before_rounds_are_kept(browser, server):
    """A page that showed all 30 questions may have saved answers past the first ten: they join the round."""
    page, errors = page_with(browser, server, {"solved": {"t_ext": [0, 1, 14, 22]}, "at": {"t_ext": 23}})
    page.locator('.mx-star[data-id="t_ext"]').click()
    playwright.expect(page.locator(".mx-qprog span").first).to_have_text("שאלה 5 מתוך 10")
    playwright.expect(page.locator(".mx-qdots i.ok")).to_have_count(4)
    assert not errors



def test_a_practice_exam_mixes_the_taught_units_and_reports_at_the_end(browser, server):
    page, errors = page_with(browser, server, {"done": {"t_ext": "2026-10-01T00:00:00+00:00"}}, no_chance=True,
                             now=datetime(2026, 11, 3, 10))
    page.evaluate("""() => { const b = document.createElement('button'); b.dataset.act = 'quiz';
        document.getElementById('mathView').append(b); b.click(); b.remove(); }""")   # the mixed quiz, as an assignment opens it
    sheet = page.locator(".mx-quiz-sheet")
    on = sheet.locator('[data-quiz-unit][aria-pressed="true"]')
    playwright.expect(on).to_have_count(4)   # before November: algebra 1-2, the kite, the isosceles triangle
    assert sorted(on.evaluate_all("els=>els.map(e=>e.dataset.quizUnit)")) == ["i", "k", "t", "t2"]
    sheet.locator('[data-quiz-unit="k"]').click()
    playwright.expect(on).to_have_count(3)
    sheet.locator('[data-quiz-unit="k"]').click()
    sheet.locator("[data-act=quiz-start]").click()
    playwright.expect(sheet.locator(".mx-quiz-dots button")).to_have_count(12)
    playwright.expect(sheet.locator("h3")).to_have_text("שאלה 1 מתוך 12")
    sheet.locator(".mx-choices button:not([data-right])").first.click()   # the first one wrong
    assert sheet.locator(".mx-ok, .mx-bad").count() == 0                # no feedback during the exam
    for _ in range(10):
        sheet.locator("[data-act=quiz-next]").click()
        sheet.locator(".mx-choices button[data-right]").first.click()
    sheet.locator("[data-act=quiz-next]").click()                       # the last one is left empty
    sheet.locator("[data-act=quiz-submit]").click()
    playwright.expect(sheet.locator(".mx-quiz-warn")).to_contain_text("שאלה אחת לא נענתה")
    sheet.locator('[data-quiz-go="0"]').click()                         # back to the first: the choice is kept
    playwright.expect(sheet.locator('.mx-choices button[aria-pressed="true"]')).to_have_count(1)
    sheet.locator('[data-quiz-go="11"]').click()
    sheet.locator("[data-act=quiz-submit]").click()                    # warned once: now it is handed in
    playwright.expect(sheet.locator("h3")).to_have_text("10 מתוך 12 נכונות")
    playwright.expect(sheet.locator(".mx-quiz-plan li")).to_have_count(1)  # the one mistake, with its skill to practise
    playwright.expect(sheet.locator(".mx-quiz-plan button[data-id]").first).to_be_visible()
    playwright.expect(sheet.locator(".mx-quiz-units-score > div")).to_have_count(4)
    p = progress_of(page)
    q = p["quizzes"][-1]
    assert (q["n"], q["right"], sorted(q["units"])) == (12, 10, ["i", "k", "t", "t2"]) and len(q["weak"]) == 2
    assert p["days"]["2026-11-03"] == 10                                  # right answers count toward today's goal
    page.locator(".mx-quiz-sheet .mx-x").click()
    assert not errors


def test_leaving_a_practice_exam_asks_first(browser, server):
    page, errors = page_with(browser, server, now=datetime(2026, 11, 3, 10))
    page.evaluate("""() => { const b = document.createElement('button'); b.dataset.act = 'quiz';
        document.getElementById('mathView').append(b); b.click(); b.remove(); }""")   # the mixed quiz, as an assignment opens it
    page.locator("[data-act=quiz-start]").click()
    page.locator(".mx-choices button").first.click()
    page.keyboard.press("Escape")
    playwright.expect(page.locator(".mx-quiz-warn")).to_contain_text("לצאת?")
    playwright.expect(page.locator(".mx-quiz-sheet")).to_be_visible()
    page.locator("[data-act=quiz-quit]").click()
    playwright.expect(page.locator(".mx-quiz-sheet")).to_be_hidden()
    assert "quizzes" not in progress_of(page)
    assert not errors


# ---------- misconception patterns ----------

def slips_at(now, *rows):
    """Mistake-log entries: (days ago, skill, tag[, via])."""
    return [{"at": (now - timedelta(days=d)).isoformat(), "id": sid, "q": 0, "m": m, "via": (via or ["practice"])[0]}
            for d, sid, m, *via in rows]


def patterns_of(page, slips, mistakes=None):
    return page.evaluate("([slips,mistakes])=>window.MathlySky.patterns({slips},mistakes||{})", [slips, mistakes])


def test_old_progress_without_a_mistake_log_loads(browser, server):
    page, errors = page_with(browser, server, {"done": {}, "comets": []})
    page.locator('.mx-star[data-id="t_ext"]').click()
    page.locator(".mx-choices button:not([data-right])").first.click()
    playwright.expect(page.locator(".mx-bad")).to_be_visible()
    assert len(progress_of(page)["slips"]) == 1
    assert not errors


def test_the_mistake_log_keeps_the_newest_500(browser, server):
    page, errors = page_with(browser, server)
    log = page.evaluate("""()=>{ const P={}; for(let i=0;i<501;i++) window.MathlySky.slip(P,"t_ext",i,"sign_mid","practice");
      return P.slips.map(s=>s.q); }""")
    assert len(log) == 500 and log[0] == 1 and log[-1] == 500
    assert not errors


def test_recurring_misconceptions_need_two_recent_and_rank_by_spread(browser, server):
    page, errors = page_with(browser, server)
    now = datetime.now(timezone.utc)
    p = patterns_of(page, slips_at(now, (20, "t_ext", "sign_mid"), (3, "t_ext", "sign_mid"), (2, "t_ext", "ext_partial"),
                                   (40, "t_ext", "move_sign"), (35, "t_ext", "move_sign")))
    assert [x["m"] for x in p["recurring"]] == ["sign_mid"]              # one ext_partial is not a pattern; move_sign is old
    p = patterns_of(page, slips_at(now, *[(1, "t_ext_eq", "move_sign")] * 4,
                                   (1, "t_ext", "sign_mid"), (2, "t_simplify", "sign_mid"), (3, "t_ext_eq", "sign_mid")))
    assert [x["m"] for x in p["recurring"]] == ["sign_mid", "move_sign"]  # three skills before four times in one
    assert p["recurring"][0]["n"] == 3 and len(p["recurring"][0]["skills"]) == 3
    assert not errors


def test_the_skill_to_practise_is_the_back_skill_or_the_most_frequent(browser, server):
    page, errors = page_with(browser, server)
    now = datetime.now(timezone.utc)
    mistakes = {"ext_partial": {"back": "t_ext"}, "sign_mid": {"back": None}}
    p = patterns_of(page, slips_at(now, (1, "t_simplify", "ext_partial"), (2, "t_simplify", "ext_partial"),
                                   (1, "t_simplify", "sign_mid"), (2, "t_simplify", "sign_mid"), (3, "t_ext", "sign_mid")), mistakes)
    practise = {x["m"]: x["practise"] for x in p["recurring"]}
    assert practise == {"ext_partial": "t_ext", "sign_mid": "t_simplify"}
    assert not errors


def test_a_pattern_that_stopped_is_shown_as_stopped_until_60_days(browser, server):
    page, errors = page_with(browser, server)
    now = datetime.now(timezone.utc)
    p = patterns_of(page, slips_at(now, *[(20, "t_ext", "sign_mid")] * 3, (70, "t_ext", "move_sign"), (75, "t_ext", "move_sign"),
                                   (20, "t_ext", "ext_partial")))
    assert p["recurring"] == [] and [x["m"] for x in p["stopped"]] == ["sign_mid"]   # once is not a pattern; 70 days is gone
    assert not errors


def test_a_wrong_review_answer_is_logged(browser, server):
    old = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    page, errors = page_with(browser, server, {"done": {"t_ext": old}, "seen": {"t_ext": old}}, no_chance=True)
    page.locator(".mx-review").click()
    page.locator(".mx-review-sheet .mx-choices button:not([data-right])").first.click()
    playwright.expect(page.locator(".mx-review-sheet .mx-bad")).to_be_visible()
    slips = progress_of(page)["slips"]
    assert [(s["id"], s["via"]) for s in slips] == [("t_ext", "review")] and slips[0]["m"]
    assert not errors


def test_a_practice_exam_logs_only_its_final_picks_when_handed_in(browser, server):
    page, errors = page_with(browser, server, now=datetime(2026, 11, 3, 10))
    page.evaluate("""() => { const b = document.createElement('button'); b.dataset.act = 'quiz';
        document.getElementById('mathView').append(b); b.click(); b.remove(); }""")   # the mixed quiz, as an assignment opens it
    sheet = page.locator(".mx-quiz-sheet")
    sheet.locator("[data-act=quiz-start]").click()
    sheet.locator(".mx-choices button:not([data-right])").first.click()   # wrong, then changed to right
    sheet.locator(".mx-choices button[data-right]").first.click()
    for i in range(1, 12):
        sheet.locator(f'[data-quiz-go="{i}"]').click()
        sheet.locator(f".mx-choices button{':not([data-right])' if i in (1, 2) else '[data-right]'}").first.click()
    assert "slips" not in progress_of(page) or not progress_of(page)["slips"]   # nothing while the exam goes on
    sheet.locator("[data-act=quiz-submit]").click()
    playwright.expect(sheet.locator("h3")).to_have_text("10 מתוך 12 נכונות")
    assert [s["via"] for s in progress_of(page)["slips"]] == ["exam", "exam"]
    assert not errors


def test_a_left_practice_exam_logs_nothing(browser, server):
    page, errors = page_with(browser, server, now=datetime(2026, 11, 3, 10))
    page.evaluate("""() => { const b = document.createElement('button'); b.dataset.act = 'quiz';
        document.getElementById('mathView').append(b); b.click(); b.remove(); }""")   # the mixed quiz, as an assignment opens it
    page.locator("[data-act=quiz-start]").click()
    page.locator(".mx-choices button:not([data-right])").first.click()
    page.locator("[data-act=quiz-quit]").click()
    page.locator("[data-act=quiz-quit]").click()
    playwright.expect(page.locator(".mx-quiz-sheet")).to_be_hidden()
    assert not progress_of(page).get("slips")
    assert not errors


def test_no_patterns_card_without_a_pattern(browser, server):
    now = datetime.now(timezone.utc)
    page, errors = page_with(browser, server, {"slips": slips_at(now, (1, "t_ext", "sign_mid"))})
    playwright.expect(page.locator(".mx-patterns")).to_have_count(0)    # once is not a pattern
    assert not errors


def test_the_patterns_card_names_the_top_mistake_and_opens_what_to_practise(browser, server):
    now = datetime.now(timezone.utc)
    slips = slips_at(now, (1, "t_simplify", "sign_mid"), (2, "t_ext_eq", "sign_mid"), (3, "t_simplify", "sign_mid"),
                     (1, "t_simplify", "ext_partial"), (4, "t_simplify", "ext_partial"))
    page, errors = page_with(browser, server, {"slips": slips}, no_chance=True)
    card = page.locator(".mx-patterns")
    playwright.expect(card).to_contain_text("טעות סימן באיבר האמצעי")       # in two skills, before one skill
    playwright.expect(card).to_contain_text("ב־2 מיומנויות")
    card.click()
    sheet = page.locator(".mx-patterns-sheet")
    playwright.expect(sheet.locator(".mx-pattern-list li")).to_have_count(2)
    playwright.expect(sheet.locator(".mx-pattern-list li").first).to_contain_text("3 פעמים ב־2 מיומנויות · לאחרונה אתמול")
    assert sheet.locator(".mx-pattern-list button[data-id]").evaluate_all("els=>els.map(e=>e.dataset.id)") == [
        "t_simplify", "t_ext"]                                           # most frequent skill; then ext_partial's back-skill
    sheet.locator('.mx-pattern-list button[data-id="t_ext"]').click()
    playwright.expect(page.locator(".mx-choices")).to_be_visible()         # the practice of t_ext is open
    playwright.expect(page.locator("#mxTitle")).to_contain_text("פילוג")
    assert not errors


def test_a_stopped_pattern_is_shown_as_a_win(browser, server):
    now = datetime.now(timezone.utc)
    page, errors = page_with(browser, server, {"slips": slips_at(now, *[(20, "t_ext", "sign_mid")] * 2)}, no_chance=True)
    card = page.locator(".mx-patterns")
    playwright.expect(card).to_contain_text("כבר לא חוזר")
    card.click()
    sheet = page.locator(".mx-patterns-sheet")
    playwright.expect(sheet).to_contain_text("כרגע אין טעות שחוזרת")
    playwright.expect(sheet.locator(".mx-pattern-list.gone li")).to_contain_text("טעות סימן באיבר האמצעי")
    assert not errors


def test_the_patterns_sheet_fits_a_phone(browser, server):
    now = datetime.now(timezone.utc)
    slips = slips_at(now, *[(1, "t_simplify", "sign_mid")] * 2, *[(1, "t_ext", "ext_partial")] * 2,
                     *[(2, "t_ext_eq", "move_sign")] * 2, *[(20, "t_ext", "sign_product")] * 2)
    page, errors = page_with(browser, server, {"slips": slips}, no_chance=True)
    page.set_viewport_size({"width": 375, "height": 812})
    for target in (".mx-patterns", None):
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        if target:
            page.locator(target).click()
            playwright.expect(page.locator(".mx-patterns-sheet .mx-pattern-list li")).to_have_count(4)
    assert not errors


def test_the_path_marks_the_skill_to_strengthen(browser, server):
    now = datetime.now(timezone.utc)
    progress = {"slips": slips_at(now, (1, "t_ext", "ext_partial"), (4, "t_simplify", "ext_partial")),
                "done": {"t_ext": now.isoformat()}, "seen": {"t_ext": now.isoformat()}}
    page, errors = page_with(browser, server, progress, no_chance=True)
    assert page.locator(".mx-star.fix").evaluate_all("els=>els.map(e=>e.dataset.id)") == ["t_ext"]   # ext_partial's back-skill
    playwright.expect(page.locator('.mx-star[data-id="t_ext"] + .mx-lbl em')).to_have_text("לחזק")
    assert not errors


def test_a_mistake_that_is_a_pattern_says_so_where_it_happens(browser, server):
    now = datetime.now(timezone.utc)
    page, errors = page_with(browser, server, {"slips": slips_at(now, (3, "t_ext_eq", "ext_partial"))}, no_chance=True)
    page.locator('.mx-star[data-id="t_simplify"]').click()
    page.locator(".mx-choices button[data-m=ext_partial]").first.click()   # the second time: now a pattern
    note = page.locator(".mx-bad .mx-pattern-note")
    playwright.expect(note).to_contain_text("2 פעמים ב־2 מיומנויות")
    playwright.expect(page.locator('.mx-bad button[data-id="t_ext"]')).to_have_count(1)   # offered once, not twice
    assert not errors


def test_a_first_mistake_has_no_pattern_note(browser, server):
    page, errors = page_with(browser, server, no_chance=True)
    page.locator('.mx-star[data-id="t_simplify"]').click()
    page.locator(".mx-choices button:not([data-right])").first.click()
    playwright.expect(page.locator(".mx-bad")).to_be_visible()
    playwright.expect(page.locator(".mx-pattern-note")).to_have_count(0)
    assert not errors


# ---- the class teacher's signals (MathlySky.attention): who needs attention, on Wednesday 4 November 2026
CLASS = {"skills": {"t_ext": "פילוג מורחב", "g_pyth": "פיתגורס"}, "units": [{"id": "t", "name": "טכניקה אלגברית 1"}]}


def attention(page, student, ctx=CLASS):
    return page.evaluate("([s, c]) => MathlySky.attention(s, c, new Date(2026, 10, 4, 12))", [student, ctx])


def kinds(found):
    return [x["kind"] for x in found]


def student(**progress):
    return {"signed_in": True, "progress": {"done": {}, "days": {}, "slips": [], **progress}, "quiz_sittings": []}


def slips(skill, *days_ago):
    return [{"at": (datetime(2026, 11, 4, 9) - timedelta(days=d)).isoformat() + "Z", "id": skill, "q": 0, "m": "x"}
            for d in days_ago]


def test_a_student_who_stopped_practising_needs_attention(browser, server):
    page, errors = page_with(browser, server)
    found = attention(page, student(days={"2026-10-27": 6}))
    assert [(x["kind"], x["text"]) for x in found] == [("inactive", "לא תרגל 8 ימים")]
    assert attention(page, student(days={"2026-10-28": 6})) != [] and attention(page, student(days={"2026-10-29": 6})) == []   # 7 days: yes; 6: no
    assert attention(page, student(days={"2026-11-02": 5})) == []
    assert attention(page, student(seen={"t_ext": "2026-11-03T10:00:00Z"}, days={"2026-10-01": 9})) == []   # the last practice counts
    assert not errors


def test_a_student_stuck_on_a_skill_is_named_with_it(browser, server):
    page, errors = page_with(browser, server)
    found = attention(page, student(days={"2026-11-03": 5}, slips=slips("t_ext", 1, 2, 3)))
    assert [(x["kind"], x["skills"]) for x in found] == [("stuck", ["t_ext"])] and "פילוג מורחב" in found[0]["text"]
    assert attention(page, student(days={"2026-11-03": 5}, slips=slips("t_ext", 1, 2))) == []        # two slips are not stuck
    assert attention(page, student(days={"2026-11-03": 5}, slips=slips("t_ext", 1, 20, 30))) == []   # old ones do not count
    assert attention(page, student(days={"2026-11-03": 5}, done={"t_ext": "2026-11-04"}, slips=slips("t_ext", 1, 2, 3))) == []
    assert attention(page, student(days={"2026-11-03": 5}, slips=slips("other", 1, 2, 3))) == []     # not a skill of the class
    assert not errors


def test_a_drop_in_practice_needs_enough_practice_to_drop_from(browser, server):
    page, errors = page_with(browser, server)
    week = lambda this, last: {"2026-11-02": this, "2026-10-27": last // 2, "2026-10-29": last - last // 2}
    assert page.evaluate("p => MathlySky.weekly(p, new Date(2026, 10, 4, 12))", {"days": week(14, 22)}) == {"thisWeek": 14, "lastWeek": 22}
    found = attention(page, student(days=week(6, 20)))
    assert kinds(found) == ["drop"] and "6" in found[0]["text"] and "20" in found[0]["text"]
    assert attention(page, student(days=week(2, 8))) == []      # 8 last week is too little to call a drop
    assert attention(page, student(days=week(10, 20))) == []    # exactly half is not less than half
    assert not errors


def test_a_low_server_grade_needs_attention_but_the_devices_does_not(browser, server):
    page, errors = page_with(browser, server)
    sit = lambda grade, at: {"id": at, "unit_id": "t", "grade": grade, "open": 0 if grade is not None else 1, "submitted_at": at}
    base = student(days={"2026-11-03": 5})
    found = attention(page, {**base, "quiz_sittings": [sit(40, "2026-11-03T10:00:00Z")]})
    assert [(x["kind"], x["unit"]) for x in found] == [("grade", "t")] and "40" in found[0]["text"]
    assert attention(page, {**base, "quiz_sittings": [sit(40, "2026-10-01T10:00:00Z"), sit(70, "2026-11-03T10:00:00Z")]}) == []   # the latest counts
    assert attention(page, {**base, "quiz_sittings": [sit(40, "2026-10-01T10:00:00Z"), sit(None, "2026-11-03T10:00:00Z")]}) != []   # an open one is no grade
    assert attention(page, {**base, "quiz_sittings": None}) == []
    assert attention(page, {**base, "progress": {**base["progress"], "uq": {"t": {"history": [{"score": 10}]}}}}) == []
    assert attention(page, {**base, "quiz_sittings": [sit(55, "2026-11-03T10:00:00Z")]}) == []   # 55 is not below 55
    # the official grade (the latest final sitting) counts over a later practice sitting, and is named as final
    final = lambda grade, at: {**sit(grade, at), "mode": "final"}
    found = attention(page, {**base, "quiz_sittings": [final(40, "2026-10-01T10:00:00Z"), sit(90, "2026-11-03T10:00:00Z")]})
    assert [x["kind"] for x in found] == ["grade"] and "בבוחן המסכם" in found[0]["text"] and "40" in found[0]["text"]
    assert attention(page, {**base, "quiz_sittings": [final(80, "2026-10-01T10:00:00Z"), sit(30, "2026-11-03T10:00:00Z")]}) == []
    assert not errors


def test_a_student_who_never_started_is_listed_only_once_signed_in(browser, server):
    page, errors = page_with(browser, server)
    assert [x["text"] for x in attention(page, {"signed_in": True, "progress": None, "quiz_sittings": []})] == ["עוד לא התחיל לתרגל"]
    assert attention(page, {"signed_in": False, "progress": None, "quiz_sittings": []}) == []
    assert not errors


# ---- the worked example and the help panel. The page is given an example for every skill, as the data will have.
HELP_EXAMPLE = {"question": "$(x + 5)(x − 2) = ?$",
                "steps": [{"do": "כופלים כל איבר בכל איבר: $x² − 2x + 5x − 10$", "why": "כך לא שוכחים אף מכפלה."},
                          {"do": "מחברים איברים דומים: $−2x + 5x = 3x$", "why": "רק איברים עם אותה חזקה מתחברים."},
                          {"do": "התוצאה: $x² + 3x − 10$", "why": "סידרנו מהחזקה הגבוהה לנמוכה."}],
                "answer": "$x² + 3x − 10$"}


def page_with_examples(browser, server, progress=None):
    """Like page_with, with a worked example added to every skill in the skills the server sends."""
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    ctx.add_init_script("Math.random=()=>0.99")
    ctx.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    ctx.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    ctx.add_init_script("try{localStorage.setItem('mathly.sound','off')}catch{}")
    if progress is not None:
        ctx.add_init_script(f"localStorage.setItem({json.dumps(KEY)},{json.dumps(json.dumps(progress))})")

    def skills(route):
        graph = route.fetch().json()
        for skill in graph["skills"]:
            skill["example"] = HELP_EXAMPLE
        route.fulfill(json=graph)

    ctx.route("**/api/math/skills", skills)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server)
    page.locator('.mx-nav [data-view="path"]').click()   # the app opens on home; the trail is on the path tab
    playwright.expect(page.locator(".mx-trail")).to_be_visible()
    return page, errors


def wrong_answer(page):
    page.locator(".mx-choices button:not([data-right])").first.click()
    playwright.expect(page.locator(".mx-bad")).to_be_visible()


def test_the_worked_example_is_offered_from_the_second_mistake_in_a_round(browser, server):
    page, errors = page_with_examples(browser, server)
    skill = page.locator(".mx-star.st-next").get_attribute("data-id")
    page.locator(".mx-star.st-next").click()
    wrong_answer(page)
    assert page.locator("[data-example]").count() == 0                       # the first mistake: only the tip
    page.locator(".mx-bad button.solid").click()                             # on to the next question
    asked = page.locator(".mx-q p").first.inner_text()
    wrong_answer(page)
    offer = page.locator(".mx-bad [data-example]")
    playwright.expect(offer).to_have_text("איך פותרים? דוגמה פתורה")
    # open it: a panel over the question, one step at a time, and the answer only at the end
    offer.click()
    help_ = page.locator(".mx-help")
    playwright.expect(help_.locator(".mx-example")).to_be_visible()
    playwright.expect(help_.locator(".mx-example-q")).to_contain_text("(x + 5)(x − 2)")
    steps = help_.locator(".mx-example-steps li")
    assert [steps.nth(i).is_visible() for i in range(3)] == [True, False, False]
    assert not help_.locator(".mx-example-answer").is_visible()
    help_.locator("[data-example-next]").click()
    assert [steps.nth(i).is_visible() for i in range(3)] == [True, True, False]
    help_.locator("[data-example-next]").click()
    playwright.expect(help_.locator("[data-example-next]")).to_have_text("הצגת התשובה")
    help_.locator("[data-example-next]").click()
    playwright.expect(help_.locator(".mx-example-answer")).to_be_visible()
    playwright.expect(help_.locator("[data-example-next]")).to_be_hidden()
    # closing returns to the same question, with the same feedback
    help_.locator("button.solid").click()
    playwright.expect(page.locator(".mx-help-wrap")).to_have_count(0)
    assert page.locator(".mx-q p").first.inner_text() == asked
    playwright.expect(page.locator(".mx-bad")).to_be_visible()
    # a third mistake offers it again; Escape closes the panel before the sheet
    page.locator(".mx-bad button.solid").click()
    wrong_answer(page)
    page.locator(".mx-bad [data-example]").click()
    playwright.expect(page.locator(".mx-help")).to_be_visible()
    page.keyboard.press("Escape")
    playwright.expect(page.locator(".mx-help-wrap")).to_have_count(0)
    playwright.expect(page.locator(".mx-sheet").first).to_be_visible()
    assert progress_of(page)["examples"][skill]["n"] == 2                    # both openings are kept
    assert not errors


def test_a_skill_without_an_example_offers_none(browser, server):
    page, errors = page_with(browser, server)               # the data has no examples yet
    page.locator(".mx-star.st-next").click()
    wrong_answer(page)
    page.locator(".mx-bad button.solid").click()
    wrong_answer(page)
    assert page.locator("[data-example]").count() == 0
    page.locator(".mx-helpbtn").click()                     # the help is there all the same
    playwright.expect(page.locator(".mx-help")).to_contain_text("לכישור הזה עוד אין דוגמה פתורה")
    assert "examples" not in progress_of(page) or progress_of(page)["examples"] == {}
    assert not errors


def test_opening_the_example_is_recorded_and_changes_neither_finishing_nor_gold(browser, server):
    page, errors = page_with_examples(browser, server)
    nxt = page.locator(".mx-star.st-next").get_attribute("data-id")
    page.locator(".mx-star.st-next").click()
    page.locator(".mx-helpbtn").click()                     # the "?" shows the example before any answer
    playwright.expect(page.locator(".mx-help .mx-example")).to_be_visible()
    from app.math_skills import algebra9
    description = next(x["description"] for x in algebra9()["skills"] if x["id"] == nxt)
    playwright.expect(page.locator(".mx-help")).to_contain_text(description.split("$")[0].strip()[:20])   # and the skill's description
    page.locator(".mx-help button.solid").click()
    p = progress_of(page)
    assert p["examples"][nxt]["n"] == 1 and p["examples"][nxt]["last"] and not p["done"].get(nxt)
    answer_skill_right(page)                                # clean first-try answers still make it gold
    playwright.expect(page.locator(".sky-cele h2").first).to_have_text("כוכב זהב!")
    while page.locator(".sky-cele [data-sky=go]").count():
        page.locator(".sky-cele [data-sky=go]").first.click()
    p = progress_of(page)
    assert p["done"][nxt] and p["gold"][nxt] and p["examples"][nxt]["n"] == 1
    assert not errors


# ---- assignments (MathlySky.assignmentState): created on 1 November 2026 (10:00 UTC), due 12 November, now Wednesday 4 November
ASSIGNMENT = {"id": "a1", "created_at": "2026-11-01T10:00:00Z", "due_on": "2026-11-12", "title": "חזרה",
              "items": [{"kind": "skill", "id": "g_pyth"}, {"kind": "unit_quiz", "unit": "g"}, {"kind": "exam", "units": ["g", "t"]}]}


def state(page, progress=None, sittings=(), now="2026-11-04T12:00:00", assignment=ASSIGNMENT):
    return page.evaluate("([a, p, s, n]) => MathlySky.assignmentState(a, p, s, new Date(n))",
                         [assignment, progress or {}, None if sittings is None else list(sittings), now])


def test_a_skill_finished_before_the_assignment_is_already_done_and_on_time(browser, server):
    page, errors = page_with(browser, server)
    got = state(page, {"done": {"g_pyth": "2026-09-20T08:00:00Z"}})
    first = got["items"][0]
    assert (first["done"], first["late"]) == (True, False) and got["doneCount"] == 1 and got["total"] == 3
    assert got["next"] == 1 and not got["finished"] and not got["overdue"]        # the next one to do is the unit quiz
    assert state(page, {})["items"][0]["done"] is False
    assert not errors


def test_a_unit_quiz_counts_only_when_handed_in_after_the_assignment_was_made(browser, server):
    page, errors = page_with(browser, server)
    before = [{"unit_id": "g", "submitted_at": "2026-10-30T09:00:00Z"}]
    after = [{"unit_id": "g", "submitted_at": "2026-11-03T09:00:00Z"}]
    other = [{"unit_id": "t", "submitted_at": "2026-11-03T09:00:00Z"}]
    assert state(page, sittings=before)["items"][1]["done"] is False
    assert state(page, sittings=other)["items"][1]["done"] is False
    assert state(page, sittings=before + after)["items"][1]["done"] is True
    assert state(page, sittings=after)["items"][1]["at"] == "2026-11-03T09:00:00Z"
    unknown = state(page, sittings=None)["items"][1]                              # the server's record could not be read
    assert (unknown["done"], unknown["known"]) == (False, False)
    assert not errors


def test_a_practice_exam_must_cover_every_unit_of_the_item_and_come_after_the_assignment(browser, server):
    page, errors = page_with(browser, server)
    exam = lambda at, *units: {"quizzes": [{"at": at, "n": 12, "right": 9, "units": list(units)}]}
    assert state(page, exam("2026-11-03T09:00:00Z", "g"))["items"][2]["done"] is False            # missing a unit
    assert state(page, exam("2026-10-30T09:00:00Z", "g", "t"))["items"][2]["done"] is False       # before the assignment
    assert state(page, exam("2026-11-03T09:00:00Z", "g", "t"))["items"][2]["done"] is True
    assert state(page, exam("2026-11-03T09:00:00Z", "t", "g", "k"))["items"][2]["done"] is True   # more units than asked is fine
    assert not errors


def test_late_means_after_the_due_day_in_jerusalem_and_overdue_means_unfinished_after_it(browser, server):
    page, errors = page_with(browser, server)
    all_done = lambda skill_at: {"done": {"g_pyth": skill_at}, "quizzes": [{"at": "2026-11-03T09:00:00Z", "units": ["g", "t"]}]}
    sit = [{"unit_id": "g", "submitted_at": "2026-11-03T09:00:00Z"}]
    on_time = state(page, all_done("2026-11-12T21:30:00Z"), sit)             # 23:30 on the 12th in Jerusalem (UTC+2)
    assert on_time["finished"] and not on_time["late"] and not on_time["overdue"]
    late = state(page, all_done("2026-11-12T22:30:00Z"), sit)                # 00:30 on the 13th
    assert late["finished"] and late["late"] and late["items"][0]["late"] and not late["items"][1]["late"]
    assert not state(page, {}, [], now="2026-11-12T20:00:00")["overdue"]      # the evening of the due day: not yet
    assert state(page, {}, [], now="2026-11-13T09:00:00")["overdue"]           # the day after, unfinished
    done_late = state(page, all_done("2026-11-02T09:00:00Z"), sit, now="2026-11-20T09:00:00")
    assert done_late["finished"] and not done_late["overdue"]                  # finished: never overdue
    assert not errors


def test_a_worksheet_is_done_when_handed_in_and_late_after_the_due_day(browser, server):
    page, errors = page_with(browser, server)
    sheet = {**ASSIGNMENT, "items": [{"kind": "worksheet", "id": "w1"}, {"kind": "skill", "id": "g_pyth"}]}
    handed = lambda at, wid="w1": {"sittings": [], "submissions": [{"worksheet_id": wid, "submitted_at": at, "score": None}]}
    on_time = page.evaluate("([a, s, n]) => MathlySky.assignmentState(a, {}, s, new Date(n))",
                            [sheet, handed("2026-11-12T20:00:00Z"), "2026-11-04T12:00:00"])
    first = on_time["items"][0]                                              # 22:00 on the due day in Jerusalem
    assert (first["done"], first["late"], first["known"]) == (True, False, True) and first["submission"]["worksheet_id"] == "w1"
    assert on_time["next"] == 1
    run = lambda server_data: page.evaluate("([a, s]) => MathlySky.assignmentState(a, {}, s, new Date('2026-11-04T12:00:00'))",
                                            [sheet, server_data])["items"][0]
    late = run(handed("2026-11-12T22:30:00Z"))                                 # 00:30 on the 13th
    assert late["done"] and late["late"]
    assert not run(handed("2026-11-03T09:00:00Z", "w2"))["done"]                # another worksheet's submission
    assert not run({"sittings": [], "submissions": []})["done"]                 # opened, not handed in
    unknown = run({"sittings": [], "submissions": None})                       # could not be read
    assert (unknown["done"], unknown["known"]) == (False, False)
    assert run([])["known"] and not run([])["done"]                            # a bare array is the sittings
    assert not errors


def test_a_returned_worksheet_is_not_done_until_handed_in_again_by_its_new_date(browser, server):
    page, errors = page_with(browser, server)
    sheet = {**ASSIGNMENT, "items": [{"kind": "worksheet", "id": "w1"}]}
    run = lambda sub, now: page.evaluate("([a, s, n]) => MathlySky.assignmentState(a, {}, s, new Date(n))",
                                         [sheet, {"sittings": [], "submissions": [sub]}, now])
    returned = {"worksheet_id": "w1", "submitted_at": "2026-11-10T09:00:00Z", "state": "returned", "return_due_on": "2026-11-16"}
    got = run(returned, "2026-11-14T12:00:00")
    assert not got["finished"] and got["items"][0]["returned"] and not got["overdue"]   # past the 12th, before the 16th
    assert run(returned, "2026-11-17T12:00:00")["overdue"]
    no_date = {**returned, "return_due_on": None}
    assert run(no_date, "2026-11-14T12:00:00")["overdue"]                     # without a new date the first one stands
    again = {"worksheet_id": "w1", "submitted_at": "2026-11-15T09:00:00Z", "state": "submitted", "version": 2,
             "earlier": [returned]}
    fixed = run(again, "2026-11-15T12:00:00")
    assert fixed["finished"] and not fixed["late"]                            # by the new date: on time
    assert not errors


def test_each_owed_item_has_one_state_in_the_tasks_order(browser, server):
    page, errors = page_with(browser, server)
    order = page.evaluate("""() => [
      {returned:true, overdue:true, waiting:true}, {overdue:true, waiting:true}, {waiting:true, checked:true},
      {checked:true, handedIn:true}, {handedIn:true, started:true}, {started:true}, {}].map(f => MathlySky.taskState(f))""")
    assert order == ["returned", "late", "waiting", "checked", "handed", "progress", "new"]
    sheet = {**ASSIGNMENT, "items": [{"kind": "worksheet", "id": "w1"}]}
    task = lambda sub, now="2026-11-04T12:00:00": page.evaluate(
        "([a, s, n]) => MathlySky.assignmentTask(a, {}, s, new Date(n))", [sheet, {"sittings": [], "submissions": [sub] if sub else []}, now])
    handed = {"worksheet_id": "w1", "submitted_at": "2026-11-03T09:00:00Z", "state": "submitted"}
    assert task(None)["state"] == "new" and task(None, "2026-11-20T12:00:00")["label"] == "באיחור"
    assert task(handed)["label"] == "ממתין לבדיקה"
    assert task({**handed, "state": "checked", "checked_at": "2026-11-05T09:00:00Z"})["label"] == "נבדק"
    assert task({**handed, "state": "returned"}, "2026-11-20T12:00:00")["label"] == "הוחזר לתיקון"   # even past the date
    skills = {**ASSIGNMENT, "items": [{"kind": "skill", "id": "g_pyth"}, {"kind": "skill", "id": "t_ext"}]}
    progress = lambda done: page.evaluate("([a, p]) => MathlySky.assignmentTask(a, p, [], new Date('2026-11-04T12:00:00')).state", [skills, {"done": done}])
    assert progress({"g_pyth": "2026-11-02T09:00:00Z"}) == "progress"
    assert progress({"g_pyth": "2026-11-02T09:00:00Z", "t_ext": "2026-11-03T09:00:00Z"}) == "handed"
    final = lambda offer: page.evaluate("o => MathlySky.finalTask(o).label", offer)
    assert final({"start": None}) == "עוד לא התחיל"
    assert final({"start": {"id": "s"}}) == "בתהליך"
    assert final({"start": {"id": "s", "sitting_id": "x"}}) == "הוגש · ממתין לתוצאות"
    assert not errors


# ---- focus areas (MathlySky.focus): where a student most needs work, with the evidence for each skill
def test_lost_quiz_points_are_split_between_the_skills_of_a_question(browser, server):
    page, errors = page_with(browser, server)
    sit = {"submitted_at": "2026-11-03T09:00:00Z", "questions": [
        {"points": 25, "earned": 10, "skills": ["t_ext", "t_ext_eq"]}, {"points": 25, "earned": None, "skills": ["t_area"]},
        {"points": 25, "earned": 25, "skills": ["t_formulas"]}]}
    lost = page.evaluate("s => MathlySky.quizLost(s, new Date('2026-11-04T12:00:00Z'))", [sit])
    assert lost == {"t_ext": 7.5, "t_ext_eq": 7.5}   # an unchecked answer adds nothing, a full one neither
    old = {**sit, "submitted_at": "2026-08-01T09:00:00Z"}
    assert page.evaluate("s => MathlySky.quizLost(s, new Date('2026-11-04T12:00:00Z'))", [old]) == {}   # over 60 days
    assert not errors


def test_the_focus_score_ranks_skills_by_their_evidence(browser, server):
    page, errors = page_with(browser, server)
    P = {"done": {"t_area": "2026-09-01T09:00:00Z"}, "seen": {"t_area": "2026-09-01T09:00:00Z", "t_simplify": "2026-11-03T09:00:00Z"},
         "slips": [{"at": "2026-11-02T09:00:00Z", "id": "t_ext", "m": "x"}] * 4, "tries": {"t_ext": 3}}
    sit = [{"submitted_at": "2026-11-03T09:00:00Z", "questions": [{"points": 25, "earned": 13, "skills": ["t_ext"]}]}]
    got = page.evaluate("([p, s]) => MathlySky.focus(p, s, ['t_ext','t_simplify','t_area','t_formulas'], new Date('2026-11-04T12:00:00Z'))", [P, sit])
    assert [x["id"] for x in got] == ["t_ext", "t_simplify", "t_area"]   # t_formulas: nothing against it
    first = got[0]
    assert (first["lost"], first["wrong"], first["unfinished"], first["fading"]) == (12, 4, True, False)
    assert got[2]["fading"] is True and got[2]["unfinished"] is False
    assert page.evaluate("() => MathlySky.focus({}, [], ['t_ext'])") == []   # no evidence, no focus area
    assert not errors


# ---------- quiz and exam names ----------
# A unit has a בוחן חיזוק (retaken) and a בוחן מסכם (once, the unit's grade); practice over several units is a מבחן
# תרגול; a מבחן is the school's exam. These earlier names are gone from every screen (a whole word: "מבחני תרגול"
# is fine, "בחני תרגול" on its own is not).
import re as _re
OLD_TERMS = ("בוחן סופי", "הבוחן הסופי", "בחנים סופיים", "בוחנים סופיים", "בוחן תרגול", "בחני תרגול", "בחני התרגול",
             "בוחן מעורב", "בחנים מעורבים", "הבוחן המעורב", "מבחני יחידה", "בוחן כמו במבחן")


def old_terms_in(text):
    return [t for t in OLD_TERMS if _re.search(rf"(?<![\u05d0-\u05ea]){t}(?![\u05d0-\u05ea])", text)]


def test_no_old_quiz_names_in_what_is_shipped():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    files = [*root.glob("static/*.js"), *root.glob("static/*.html"), *root.glob("app/*.py")]
    found = [f"{f.name}: {t}" for f in files for t in old_terms_in(f.read_text(encoding="utf-8"))]
    assert not found


def test_the_student_home_and_the_guide_show_no_old_quiz_names(browser, server):
    page, errors = page_with(browser, server)
    home = page.locator("#mathView").inner_text()
    page.locator("#mathView [data-guide-open]").first.click()
    playwright.expect(page.locator("#mgS")).to_be_visible()
    text = home + page.get_by_role("dialog", name="איך משתמשים באפליקציה").text_content()   # both tabs, the hidden one too
    assert not old_terms_in(text)
    assert not errors


# ---- quizzes chosen for each student (MathlySky.chance / pickQuiz)
NOW = "2026-11-04T12:00:00Z"


def chance(page, P, skill):
    return page.evaluate("([p, id, now]) => MathlySky.chance(p, id, new Date(now))", [P, skill, NOW])


def test_a_wrong_answer_is_counted_for_its_skill(browser, server):
    page, errors = page_with(browser, server)
    page.locator('.mx-star.st-next').click()
    page.locator(".mx-choices button:not([data-right])").first.click()
    assert progress_of(page)["wrongs"] == {"t_ext": 1}
    assert not errors


def test_the_chance_of_a_right_answer_follows_the_answers_and_the_stars(browser, server):
    page, errors = page_with(browser, server)
    recent, old = "2026-11-03T09:00:00Z", "2026-09-01T09:00:00Z"
    assert chance(page, {"tries": {"a": 4}}, "a") is None                                   # under 5 answers: unknown
    assert chance(page, {"tries": {"a": 8}, "wrongs": {"a": 2}}, "a") == pytest.approx(.7)   # (6 + 1) / (8 + 2)
    slips = [{"at": recent, "id": "a", "m": "x"}] * 3
    assert chance(page, {"tries": {"a": 8}, "wrongs": {"a": 1}, "slips": slips}, "a") == pytest.approx(.6)   # the slips' history counts
    weak_done = {"tries": {"a": 10}, "wrongs": {"a": 8}, "done": {"a": recent}, "seen": {"a": recent}}
    assert chance(page, weak_done, "a") == pytest.approx(.8)                                 # finished: at least 0.8
    assert chance(page, {**weak_done, "gold": {"a": recent}}, "a") == pytest.approx(.9)      # gold: at least 0.9
    assert chance(page, {**weak_done, "done": {"a": old}, "seen": {"a": old}}, "a") == pytest.approx(.7)   # fading: 0.1 less
    assert not errors


def pick(page, P, pool, **options):
    return page.evaluate("([p, pool, o, now]) => MathlySky.pickQuiz(p, pool, {...o, now: new Date(now)})", [P, pool, options, NOW])


def class_of_twelve():
    """4 started and not finished (chance 0.65), 8 finished (0.8 and more), 2 never practised."""
    recent = "2026-11-03T09:00:00Z"
    P, pool = {"tries": {}, "wrongs": {}, "done": {}, "seen": {}}, []
    for i in range(4):
        P["tries"][f"c{i}"], P["wrongs"][f"c{i}"], P["seen"][f"c{i}"] = 18, 6, recent   # (12 + 1) / 20 = 0.65
        pool.append({"id": f"c{i}", "qs": list(range(10)), "rank": i})
    for i in range(8):
        P["tries"][f"s{i}"], P["done"][f"s{i}"], P["seen"][f"s{i}"] = 12, recent, recent
        pool.append({"id": f"s{i}", "qs": list(range(10)), "rank": 10 + i})
    pool += [{"id": "n0", "qs": [0, 1], "rank": 99}, {"id": "n1", "qs": [0, 1], "rank": 98}]
    return P, pool


def test_quiz_one_aims_at_70_percent_mostly_from_near_mastered_topics(browser, server):
    page, errors = page_with(browser, server)
    P, pool = class_of_twelve()
    one = pick(page, P, pool, target=.7)
    two = pick(page, P, pool, target=.8)
    near = lambda r: sum(x["id"].startswith("c") for x in r["items"])
    assert len(one["items"]) == 12 and .65 <= one["expected"] <= .75
    assert len(two["items"]) == 12 and .75 <= two["expected"] <= .85
    assert near(one) > 6 and near(two) < near(one)                         # quiz 2 has more finished topics
    for r in (one, two):
        assert not [x for x in r["items"] if x["id"].startswith("n")]      # never practised: never asked
        per = {}
        for x in r["items"]:
            per[x["id"]] = per.get(x["id"], 0) + 1
        assert max(per.values()) <= 3                                      # at most 3 a topic
    assert not errors


def test_a_retake_draws_questions_not_seen_before(browser, server):
    page, errors = page_with(browser, server)
    P, pool = class_of_twelve()
    first = pick(page, P, pool, target=.7)
    seen = {f'{x["id"]}:{x["qi"]}': "2026-11-03T10:00:00Z" for x in first["items"]}
    second = pick(page, P, pool, target=.7, seen=seen)
    assert not {f'{x["id"]}:{x["qi"]}' for x in second["items"]} & set(seen)
    # a topic whose questions were all seen: the one seen longest ago comes first
    small = [{"id": "c0", "qs": [0, 1], "rank": 0}]
    got = pick(page, P, small, target=.7, n=1, seen={"c0:0": "2026-11-03T10:00:00Z", "c0:1": "2026-11-01T10:00:00Z"})
    assert got["items"] == [{"id": "c0", "qi": 1}]
    assert not errors


def test_a_student_with_few_answers_gets_the_most_recently_taught_topics(browser, server):
    page, errors = page_with(browser, server)
    P = {"tries": {"a": 2, "b": 2, "c": 2}, "seen": {"a": NOW, "b": NOW, "c": NOW}}
    pool = [{"id": "a", "qs": list(range(10)), "rank": 1}, {"id": "b", "qs": list(range(10)), "rank": 3},
            {"id": "c", "qs": list(range(10)), "rank": 2}, {"id": "z", "qs": list(range(10)), "rank": 9}]
    got = pick(page, P, pool, target=.7, n=6)
    assert [x["id"] for x in got["items"]][:3] == ["b", "c", "a"] and got["unknown"] == 6   # newest first, by turns
    assert "z" not in {x["id"] for x in got["items"]}
    # too few questions to fill the quiz: it is shorter
    assert len(pick(page, P, [{"id": "a", "qs": [0, 1, 2, 3], "rank": 1}], target=.7)["items"]) == 4
    assert not errors
