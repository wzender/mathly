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
    app = create_app(auth=ScanAuth()); app.state.answers = answer_store
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
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן מסכם")
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
            playwright.expect(sheet.locator("h3")).to_have_text("בוחן מסכם: 65/100", timeout=20000)   # 25 + 15 + 25 + 0
            playwright.expect(sheet.locator(".mx-uq-verdict")).to_have_text(["נכון ומלא", "נכון בחלקו", "נכון ומלא", "לא צולמה תשובה"])
            playwright.expect(sheet.locator(".mx-uq-qhead span")).to_have_text(["25/25 נק׳", "15/25 נק׳", "25/25 נק׳", "0/25 נק׳"])
            assert len(calls) == 3
            page.locator(".mx-uq-sheet .mx-x").click()
            playwright.expect(page.locator('.mx-uquiz[data-uquiz="t"]')).to_have_attribute("aria-label", "בוחן מסכם: טכניקה אלגברית 1, 65/100")
            page.reload()   # the result stays, and opening it again does not check again
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('.mx-uquiz[data-uquiz="t"]').click()
            page.locator("[data-uq-result]").first.click()
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן מסכם: 65/100", timeout=10000)
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
            playwright.expect(page.locator('.mx-uquiz[data-uquiz="k"]')).to_have_attribute("aria-label", "בוחן מסכם: דלתון, בתהליך")
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
            playwright.expect(page.locator(".mx-uq-sheet h3")).to_have_text("בוחן מסכם: 20/100", timeout=20000)
            playwright.expect(page.locator(".mx-uq-sheet .mx-src")).to_contain_text("הוגש כשהזמן נגמר")
            assert len(calls) == 1 and not errors
        finally:
            browser.close()
