"""The summarizing quiz at the end of a unit: its content, its API, and the paper quiz in a browser.
Answers are kept in real PostgreSQL (scan_support); the AI check is a stand-in."""
import asyncio
import copy
import json
import socket
import threading
import time

import uvicorn

import httpx
import pytest

from app.answer_grading import validate_assessment
from app.main import create_app
from app.math_skills import algebra9, practice_graph, problems, question_version, quiz_snapshot
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server
from test_answer_grading import assessment
from test_answer_scans import png

QUIZ_UNITS = ["t", "t2", "k", "i"]


@pytest.fixture(autouse=True)
def unlocked_open_ended(monkeypatch):
    monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")


def test_the_units_taught_first_end_with_a_quiz_worth_100():
    units = {u["id"]: u for u in algebra9()["units"]}
    for uid in QUIZ_UNITS:
        quiz = units[uid]["quiz"]
        assert quiz["minutes"] == 45 and sum(q["points"] for q in quiz["questions"]) == 100
        assert all("choices" not in q for q in quiz["questions"])


def test_a_broken_quiz_is_named():
    graph = copy.deepcopy(algebra9())
    t = next(u for u in graph["units"] if u["id"] == "t")
    t["quiz"]["questions"][0]["points"] = 30
    t["quiz"]["minutes"] = 0
    k = next(u for u in graph["units"] if u["id"] == "k")
    k["quiz"]["questions"][0]["figure"] = "A=0,0; B=1,0; poly A B Z"
    found = problems(graph)
    assert "t quiz: minutes must be a whole number from 5 to 120" in found
    assert "k quiz question 1: figure names unknown point Z" in found
    t["quiz"]["minutes"] = 45
    assert "t quiz: points add up to 105, not 100" in problems(graph)


def test_the_quiz_is_open_only_with_answer_storage_and_grading():
    units = lambda g: {u["id"]: u for u in g["units"]}
    assert units(practice_graph(True, False))["t"]["quiz"]["locked"] is False
    assert units(practice_graph(False, False))["t"]["quiz"]["locked"] is True
    assert units(practice_graph(True, True))["t"]["quiz"]["locked"] is True
    q = units(practice_graph(True, False))["k"]["quiz"]["questions"][1]
    assert q["question_version"] == question_version(quiz_snapshot(units(algebra9())["k"], 1))


def test_quiz_answers_are_kept_and_checked_only_when_asked(answer_store, monkeypatch):
    store = answer_store
    app = create_app(auth=ScanAuth()); app.state.answers = store
    calls = []

    class Grader:
        def grade(self, image, snapshot):
            calls.append(snapshot)
            return validate_assessment(assessment(score=100))
    app.state.answer_grader = Grader()
    t = next(u for u in algebra9()["units"] if u["id"] == "t")
    version = question_version(quiz_snapshot(t, 2))

    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                                     headers={"Authorization": f"Bearer {OWNER}"}) as c:
            url = "/api/math/quiz-attempts"
            assert (await c.post(url, json={"unit": "t", "index": 9, "question_version": version})).status_code == 404
            assert (await c.post(url, json={"unit": "q", "index": 0, "question_version": version})).status_code == 404
            changed = await c.post(url, json={"unit": "t", "index": 2, "question_version": "old"})
            assert (changed.status_code, changed.json()["detail"]) == (409, "question_changed")
            first = (await c.post(url, json={"unit": "t", "index": 2, "question_version": version, "new": True})).json()
            aid = first["attempt"]["id"]
            assert first["attempt"]["question_id"] == "quiz:t:2"
            assert first["attempt"]["snapshot"]["points"] == 25 and "בוחן מסכם" in first["attempt"]["snapshot"]["name"]
            again = (await c.post(url, json={"unit": "t", "index": 2, "question_version": version})).json()
            assert again["attempt"]["id"] == aid                                   # the sitting's attempt continues
            other = await c.get(f"/api/math/answer-attempts/{aid}", headers={"Authorization": f"Bearer {OTHER}"})
            assert other.status_code == 404
            # the same steps as the page: request, confirm, lease, upload
            scan = (await c.post(f"/api/math/answer-attempts/{aid}/scans", json={"renew": True})).json()["scan"]
            await c.post(f"/api/math/answer-scans/{scan['id']}/confirm")
            lease = (await c.post(f"/api/math/answer-scans/{scan['id']}/uploads", json={"key": "9f0d6c3e-8c51-4a51-9c7e-0d5f4b8a1e11"})).json()
            up = await c.post(f"/api/math/answer-scans/{scan['id']}/uploads/{lease['lease_id']}",
                              files={"photo": ("a.png", png(), "image/png")})
            assert up.status_code == 200 and up.json()["attachment"]
            await asyncio.sleep(.2)
            assert not calls and up.json()["grading"] is None                      # not checked on upload
            graded = (await c.post(f"/api/math/answer-attempts/{aid}/grade", json={})).json()
            assert graded["grading"]["result"]["score"] == 100
            assert calls == [first["attempt"]["snapshot"]]
            monkeypatch.setenv("MATHLY_OPEN_ENDED_LOCKED", "1")
            locked = await c.post(url, json={"unit": "t", "index": 2, "question_version": version})
            assert (locked.status_code, locked.json()["detail"]) == (403, "open_ended_locked")
    asyncio.run(run())


playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def quiz_server(answer_store):
    """The app with real answer storage, and an AI check that scores by question: 100, 60, 100, ..."""
    auth = ScanAuth()
    auth.developers = frozenset({OWNER + "@test.invalid"})   # OWNER manages (a developer), so it may review its own answers
    app = create_app(auth=auth); app.state.answers = answer_store
    calls = []

    class Grader:
        def grade(self, image, snapshot):
            calls.append(snapshot["name"])
            return validate_assessment(assessment(score=60, reasoning_correct=False) if snapshot["name"].endswith("2")
                                       else assessment(score=100))
    app.state.answer_grader = Grader()
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            while not server.started:
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}", calls
        finally:
            server.should_exit = True; thread.join(timeout=5)


def signed_in(p, url, mobile=True):
    from test_answer_browser import session
    browser = p.chromium.launch()
    page = session(browser, mobile=mobile).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.locator('.mx-nav [data-view="path"]').click()
    return browser, page, errors


def photograph(page, i, tmp_path):
    f = tmp_path / f"answer{i}.png"
    f.write_bytes(png())
    with page.expect_file_chooser() as chooser:
        page.locator(f'[data-uq-photo="{i}"]').click()
    chooser.value.set_files(str(f))
    playwright.expect(page.locator(f'[data-uq-i="{i}"] [role=status]')).to_have_text("✓ התשובה נשמרה", timeout=10000)


def test_a_unit_quiz_is_written_photographed_handed_in_and_then_checked(quiz_server, tmp_path):
    url, calls = quiz_server
    with playwright.sync_playwright() as p:
        browser, page, errors = signed_in(p, url)
        try:
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בחני היחידה")
            page.locator("[data-act=uq-start]").click()
            paper = page.locator(".mx-uq-paper")
            playwright.expect(paper.locator(".mx-uq-q")).to_have_count(4)
            playwright.expect(paper.locator(".mx-uq-clock")).to_have_text(__import__("re").compile(r"^4[45]:\d\d$"))
            for i in range(3):   # the last question is left without an answer
                photograph(page, i, tmp_path)
            photograph(page, 1, tmp_path)   # a retake replaces the answer
            assert not calls                # nothing is checked before handing in
            paper.locator("[data-act=uq-submit]").click()
            playwright.expect(paper.locator(".mx-quiz-warn")).to_contain_text("0 נקודות")
            paper.locator("[data-act=uq-submit]").click()
            sheet = page.locator(".mx-uq-sheet")
            playwright.expect(sheet.locator("h3")).to_have_text("בוחן חיזוק: 65/100", timeout=20000)   # 25 + 15 + 25 + 0
            playwright.expect(sheet.locator(".mx-uq-verdict")).to_have_text(["נכון ומלא", "נכון בחלקו", "נכון ומלא", "לא צולמה תשובה"])
            playwright.expect(sheet.locator(".mx-uq-qhead span")).to_have_text(["25/25 נק׳", "15/25 נק׳", "25/25 נק׳", "0/25 נק׳"])
            assert len(calls) == 3
            # before a retake: the skills of the questions that lost points (question 2 and the missing question 4)
            playwright.expect(sheet.locator(".mx-uq-retake .mx-chip")).to_have_count(2)
            assert sorted(sheet.locator(".mx-uq-retake .mx-chip").evaluate_all("b=>b.map(x=>x.dataset.id)")) == ["t_ext_eq", "t_formulas"]
            playwright.expect(sheet.locator('.mx-quiz-nav [data-uquiz="t"]')).to_have_text("ניסיון נוסף")
            page.locator(".mx-uq-sheet .mx-x").click()
            playwright.expect(page.locator('.mx-uquiz[data-uquiz="t"]')).to_have_attribute("aria-label", "בחני היחידה: טכניקה אלגברית 1, 65/100")
            page.reload()   # the result stays, and opening it again does not check again
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            page.locator("[data-uq-result]").first.click()
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן חיזוק: 65/100", timeout=10000)
            assert len(calls) == 3 and not errors
            # a score written into this device's progress does not change what the result screen shows
            page.evaluate("""() => { for (const k of Object.keys(localStorage)) if (k.startsWith('mathly.progress.v1:')) {
                const p = JSON.parse(localStorage.getItem(k)); p.uq.t.history.at(-1).score = 100;
                localStorage.setItem(k, JSON.stringify(p)); } }""")
            page.reload()
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            page.locator("[data-uq-result]").first.click()
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן חיזוק: 65/100", timeout=10000)
            playwright.expect(page.locator(".mx-uq-qhead span")).to_have_text(["25/25 נק׳", "15/25 נק׳", "25/25 נק׳", "0/25 נק׳"])
            assert len(calls) == 3 and not errors
        finally:
            browser.close()


def test_when_the_time_and_the_photo_minutes_are_over_the_quiz_is_handed_in(quiz_server, tmp_path):
    url, calls = quiz_server
    with playwright.sync_playwright() as p:
        browser, page, errors = signed_in(p, url)
        try:
            page.locator('.mx-uquiz[data-uquiz="k"]').click()
            page.locator("[data-act=uq-start]").click()
            photograph(page, 0, tmp_path)
            page.locator(".mx-uq-paper .mx-x").click()   # leaving does not stop the clock
            playwright.expect(page.locator('.mx-uquiz[data-uquiz="k"]')).to_have_attribute("aria-label", "בחני היחידה: דלתון, בתהליך")
            page.evaluate("""()=>{ const k=Object.keys(localStorage).find(k=>k.startsWith('mathly.progress.v1:'));
              const P=JSON.parse(localStorage.getItem(k)); P.uq.k.sitting.started-=50*60000; localStorage.setItem(k,JSON.stringify(P)); }""")
            page.reload()
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="k"]').click()   # 50 minutes in: the photo minutes are running
            playwright.expect(page.locator(".mx-uq-banner")).to_contain_text("הזמן לכתיבה נגמר")
            page.locator(".mx-uq-paper .mx-x").click()
            page.evaluate("""()=>{ const k=Object.keys(localStorage).find(k=>k.startsWith('mathly.progress.v1:'));
              const P=JSON.parse(localStorage.getItem(k)); P.uq.k.sitting.started-=10*60000; localStorage.setItem(k,JSON.stringify(P)); }""")
            page.reload()
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="k"]').click()   # over: handed in as it is, and checked
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן חיזוק: 20/100", timeout=20000)
            playwright.expect(page.locator(".mx-uq-sheet .mx-src")).to_contain_text("הוגש כשהזמן נגמר")
            assert len(calls) == 1 and not errors
        finally:
            browser.close()


def test_the_unit_quiz_has_a_board_with_a_tab_per_question(quiz_server):
    from test_board_browser import draw_line, ink_pixels
    url, _ = quiz_server
    with playwright.sync_playwright() as p:
        browser, page, errors = signed_in(p, url, mobile=False)
        try:
            page.set_viewport_size({"width": 1440, "height": 900})
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            page.locator("[data-act=uq-start]").click()
            playwright.expect(page.locator(".mx-uq-paper .mx-uq-q")).to_have_count(4)
            page.locator("[data-board-toggle]").click()
            tabs = page.locator(".mx-board-pages [data-page]")
            playwright.expect(tabs).to_have_count(4)
            draw_line(page)
            assert ink_pixels(page) > 50
            tabs.nth(1).click()
            assert ink_pixels(page) == 0
            playwright.expect(tabs.nth(0)).to_have_class("has")   # the tab with a sketch stands out
            tabs.nth(0).click()
            assert ink_pixels(page) > 50
            assert errors == []
        finally:
            browser.close()


def test_a_unit_quiz_answer_is_handed_in_from_the_board(quiz_server):
    from test_board_browser import draw_line
    url, _ = quiz_server
    with playwright.sync_playwright() as p:
        browser, page, errors = signed_in(p, url, mobile=False)
        try:
            page.set_viewport_size({"width": 1440, "height": 900})
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            page.locator("[data-act=uq-start]").click()
            page.locator('[data-uq-board="2"]').click()   # each question opens the board on its own page
            playwright.expect(page.locator(".mx-board")).to_be_visible()
            playwright.expect(page.locator('.mx-board-pages [data-page="2"]')).to_have_attribute("aria-selected", "true")
            send = page.locator(".mx-board-send")
            playwright.expect(send).to_have_text("הגשה לשאלה 3")
            send.click()   # an empty page is not handed in
            playwright.expect(send).to_contain_text("הלוח ריק")
            draw_line(page)
            page.wait_for_timeout(2600)
            send.click()
            playwright.expect(page.locator('[data-uq-i="2"] [role=status]')).to_have_text("✓ התשובה נשמרה", timeout=10000)
            playwright.expect(page.locator('[data-uq-i="2"] img.mx-uq-img')).to_be_visible()
            playwright.expect(send).to_contain_text("הוגשה לשאלה 3")
            playwright.expect(page.locator("[data-uq-count]")).to_have_text("צולמו 1 מתוך 4 תשובות")
            assert errors == []
        finally:
            browser.close()


def test_on_a_phone_a_unit_quiz_answer_is_handed_in_from_the_full_screen_board(quiz_server):
    url, _ = quiz_server
    with playwright.sync_playwright() as p:
        browser, page, errors = signed_in(p, url, mobile=True)
        try:
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            page.locator("[data-act=uq-start]").click()
            page.locator('[data-uq-board="1"]').click()   # the student picks the board over a photo
            board = page.locator(".mx-board.full")
            playwright.expect(board).to_be_visible()
            playwright.expect(page.locator('.mx-board-pages [data-page="1"]')).to_have_attribute("aria-selected", "true")
            box = board.locator("canvas").bounding_box()
            x, y = box["x"] + 60, box["y"] + 200
            page.mouse.move(x, y); page.mouse.down()
            for k in range(1, 10):
                page.mouse.move(x + k * 25, y + (k % 2) * 20)
            page.mouse.up()
            page.locator(".mx-board-send").click()
            playwright.expect(page.locator(".mx-board-send")).to_contain_text("הוגשה לשאלה 2", timeout=10000)
            page.locator(".mx-board-back").click()
            playwright.expect(page.locator('[data-uq-i="1"] [role=status]')).to_have_text("✓ התשובה נשמרה", timeout=10000)
            assert errors == []
        finally:
            browser.close()


# ---- sittings kept on the server (app/quiz_grades.py)
def quiz_answer(store, index, *, unit="t", photo=True, owner=OWNER):
    """A fresh attempt at quiz question `index` of `unit`, with a saved photo when asked."""
    from test_answer_scans import begin, finish
    graph_unit = next(u for u in algebra9()["units"] if u["id"] == unit)
    snapshot = quiz_snapshot(graph_unit, index)
    made = store.action(owner, "resume", question_id=f"quiz:{unit}:{index}", question_version=question_version(snapshot),
                        snapshot=snapshot, new=True)
    aid = made["attempt"]["id"]
    if photo:
        scan = store.action(owner, "create_scan", attempt_id=aid)
        finish(store, begin(store, scan))
    return aid


def check(store, aid, score, owner=OWNER):
    import uuid
    lease = str(uuid.uuid4())
    store.grade(owner, "start", attempt_id=aid, lease_id=lease)
    store.grade(owner, "complete", attempt_id=aid, lease_id=lease, result=validate_assessment(assessment(score=score)))


def test_the_sittings_migration_is_additive_and_service_only(answer_store):
    import psycopg
    with answer_store.connect() as c:
        assert c.execute("select name from classes").fetchone()[0] == "existing math class"
        assert c.execute("select relrowsecurity from pg_class where relname='math_quiz_sittings'").fetchone()[0]
        c.execute("set role authenticated")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select * from math_quiz_sittings")
        c.execute("reset role")
        c.execute("set role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select math_quiz_action(null,'report','{\"users\":[]}')")


def sitting_app(store):
    app = create_app(auth=ScanAuth()); app.state.answers = store
    return app


def api(app, user=OWNER):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test",
                             headers={"Authorization": f"Bearer {user}"})


def test_handing_in_keeps_a_sitting_with_a_grade_from_the_stored_checks(answer_store):
    store = answer_store
    ids = [quiz_answer(store, i, photo=i < 3) for i in range(4)]   # the last question has no photo
    for aid, score in zip(ids[:3], (100, 60, 80)):
        check(store, aid, score)
    key = "9f0d6c3e-8c51-4a51-9c7e-0d5f4b8a1e11"
    app = sitting_app(store)

    async def run():
        async with api(app) as c:
            r = await c.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "client_key": key})
            assert r.status_code == 200
            sitting = r.json()
            assert sitting["unit_id"] == "t" and sitting["attempts"] == ids
            assert sitting["grade"] == 25 + 15 + 20 + 0 and sitting["open"] == 0
            again = (await c.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids, "client_key": key,
                                                                   "time_up": True})).json()
            assert again["id"] == sitting["id"]                                   # a lost response, sent again
            mine = (await c.get("/api/math/quiz-sittings", params={"unit_id": "t"})).json()["sittings"]
            assert [s["id"] for s in mine] == [sitting["id"]]
            assert (await c.get("/api/math/quiz-sittings", params={"unit_id": "k"})).json() == {"sittings": []}
    asyncio.run(run())
    with answer_store.connect() as c:
        assert c.execute("select count(*) from math_quiz_sittings").fetchone()[0] == 1


def test_a_sitting_with_the_wrong_attempts_is_refused(answer_store):
    store = answer_store
    ids = [quiz_answer(store, i) for i in range(4)]
    theirs = quiz_answer(store, 0, owner=OTHER, photo=False)
    other_unit = quiz_answer(store, 0, unit="k")
    app = sitting_app(store)
    post = lambda c, attempts, key, unit="t": c.post("/api/math/quiz-sittings",
                                                      json={"unit_id": unit, "attempts": attempts, "client_key": key})
    keys = [f"00000000-0000-4000-8000-00000000000{i}" for i in range(6)]

    async def run():
        async with api(app) as c:
            assert (await post(c, [theirs] + ids[1:], keys[0])).status_code == 409            # another student's
            assert (await post(c, [ids[1], ids[0], ids[2], ids[3]], keys[1])).status_code == 409   # wrong order
            assert (await post(c, [other_unit] + ids[1:], keys[2])).status_code == 409        # another unit's question
            assert (await post(c, ids[:3], keys[3])).status_code == 404                       # a question short
            assert (await post(c, ids, keys[4], unit="nope")).status_code == 404
            assert (await post(c, ["x"] * 4, keys[5])).status_code == 404                     # not attempt ids
            assert (await post(c, ids, keys[0])).status_code == 200
            reused = await post(c, ids, keys[1])                                              # the same attempts again
            assert (reused.status_code, reused.json()["detail"]) == (409, "invalid_sitting")
    asyncio.run(run())
    with answer_store.connect() as c:
        assert c.execute("select count(*) from math_quiz_sittings").fetchone()[0] == 1


def test_a_check_that_finishes_after_handing_in_gives_the_sitting_its_grade(answer_store):
    store = answer_store
    ids = [quiz_answer(store, i) for i in range(4)]
    for aid in ids[:3]:
        check(store, aid, 100)
    app = sitting_app(store)

    async def run():
        async with api(app) as c:
            first = (await c.post("/api/math/quiz-sittings", json={"unit_id": "t", "attempts": ids,
                                  "client_key": "9f0d6c3e-8c51-4a51-9c7e-0d5f4b8a1e11"})).json()
            assert first["grade"] is None and first["open"] == 1
            assert first["questions"][3]["state"] == "waiting"
            check(store, ids[3], 40)                                  # for example the teacher sends it from the queue
            mine = (await c.get("/api/math/quiz-sittings", params={"unit_id": "t"})).json()["sittings"]
            assert mine[0]["grade"] == 85 and mine[0]["open"] == 0
    asyncio.run(run())


def test_a_quiz_result_shows_the_teachers_words_and_the_home_screen_tells_about_them(quiz_server, answer_store):
    """A sitting handed in and checked, then the teacher (OWNER is a manager in these tests) reviews one answer: the
    student's home screen says so, the result shows the teacher above the AI's check, and the student can ask again."""
    import uuid
    url, calls = quiz_server
    store = answer_store
    ids = [quiz_answer(store, i) for i in range(4)]
    for aid, score in zip(ids, (100, 60, 100, 40)):
        check(store, aid, score)
    headers = {"Authorization": f"Bearer {OWNER}"}
    sitting = httpx.post(url + "/api/math/quiz-sittings", headers=headers, json={
        "unit_id": "t", "attempts": ids, "client_key": str(uuid.uuid4())}).json()
    review = httpx.put(url + f"/api/teacher/answers/{ids[1]}/review", headers=headers,
                       json={"score": 90, "comment": "הדרך נכונה, שימו לב לסימן"})
    assert review.status_code == 200
    entry = {"at": "2026-11-04T09:00:00.000Z", "attempts": ids, "score": None, "timeUp": False,
             "ck": str(uuid.uuid4()), "sid": sitting["id"]}
    seed = json.dumps(json.dumps({"uq": {"t": {"history": [entry]}}}))
    key = json.dumps("mathly.progress.v1:" + OWNER + "@test.invalid")
    from test_answer_browser import session
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            context = session(browser, mobile=True)
            context.add_init_script(f"if(!localStorage.getItem({key})) localStorage.setItem({key},{seed})")
            page = context.new_page(); errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url)
            page.locator('.mx-nav [data-view="home"]').click()
            notice = page.locator(".mx-teacher-comment")
            playwright.expect(notice).to_contain_text("המורה הגיב על תשובה שלכם")
            playwright.expect(notice).to_contain_text("90/100")
            notice.click()
            sheet = page.locator(".mx-uq-sheet")
            playwright.expect(sheet.locator("h3")).to_have_text("בוחן חיזוק: 83/100", timeout=15000)   # 25 + 23 + 25 + 10
            second = sheet.locator(".mx-uq-q").nth(1)
            playwright.expect(second.locator(".mx-teacher-note")).to_contain_text("הערת המורה")
            playwright.expect(second.locator(".mx-teacher-note")).to_contain_text("90/100")
            playwright.expect(second.locator(".mx-teacher-note")).to_contain_text("שימו לב לסימן")
            playwright.expect(second.locator(".mx-uq-verdict")).to_have_text("נבדק על ידי המורה")
            playwright.expect(second.locator(".mx-uq-qhead span")).to_have_text("23/25 נק׳")
            playwright.expect(second).to_contain_text("בדיקה אוטומטית:")
            assert sheet.locator(".mx-teacher-note").count() == 1           # only the reviewed answer has one
            # the student asks the teacher to look again at the third answer
            third = sheet.locator(".mx-uq-q").nth(2)
            third.locator(".mx-ask summary").click()
            third.locator("[data-ask-msg]").fill("כתבתי את כל השלבים")
            third.locator("[data-ask-review]").click()
            playwright.expect(third.locator(".mx-ask-wait")).to_contain_text("הבקשה ממתינה")
            listed = httpx.get(url + "/api/teacher/review-requests", headers=headers).json()["requests"]
            assert [(x["attempt_id"], x["message"]) for x in listed] == [(ids[2], "כתבתי את כל השלבים")]
            # the answer was opened: the notice is gone, and stays gone after a reload
            page.locator(".mx-uq-sheet .mx-x, .mx-uq-sheet [data-act=close]").first.click()
            playwright.expect(page.locator(".mx-teacher-comment")).to_have_count(0)
            page.reload(); page.locator('.mx-nav [data-view="home"]').click()
            playwright.expect(page.locator(".mx-continue")).to_be_visible()
            playwright.expect(page.locator(".mx-teacher-comment")).to_have_count(0)
            assert not errors
        finally:
            browser.close()
