""""תצוגה ככיתה": a developer or a teacher who is in no class previews the student screens as a class (its tests, assignments, subjects)."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_boardwork_api import auth

KID, TEACHER, OTHER, DEV = "kid@school.test", "t@school.test", "t2@school.test", "dev@school.test"


def world():
    bank, store = load_bank(), InMemoryStore()
    mine = store.create_class("setup", "ט מצוינות", lessons=[l["id"] for l in bank.lessons], teacher_email=TEACHER)
    other = store.create_class("setup", "ט 2", lessons=[l["id"] for l in bank.lessons], teacher_email=OTHER)
    store.add_member(mine["id"], KID)
    soon = store.create_test(mine["id"], clock.school_day() + timedelta(days=1), ["t", "t2"], TEACHER, created_at=clock.now() - timedelta(days=20))
    later = store.create_test(mine["id"], clock.school_day() + timedelta(days=43), ["q", "q2"], TEACHER, created_at=clock.now())
    store.create_test(other["id"], clock.school_day() + timedelta(days=5), ["k"], OTHER, created_at=clock.now())
    store.create_assignment(mine["id"], "דף עבודה", clock.school_day() + timedelta(days=3), TEACHER, "pages", pages=["1"])
    app = create_app(Settings(teachers=frozenset({TEACHER, OTHER}), developers=frozenset({DEV})), bank=bank, store=store)
    client = TestClient(app)
    for who in (KID, TEACHER, OTHER, DEV):
        client.get("/api/me", headers=auth(who))
    return client, mine, other, soon, later


def as_class(who, class_id):
    return {**auth(who), "X-View-Class": str(class_id)}


def test_a_developer_previews_any_class_and_sees_what_its_student_sees():
    client, mine, other, soon, later = world()
    assert [c["name"] for c in client.get("/api/me", headers=auth(DEV)).json()["preview"]] == ["ט מצוינות", "ט 2"]
    assert client.get("/api/home", headers=auth(DEV)).json()["tests"] == []                    # no class picked: no tests
    student = client.get("/api/home", headers=auth(KID)).json()
    dev = client.get("/api/home", headers=as_class(DEV, mine["id"])).json()
    assert [t["id"] for t in dev["tests"]] == [t["id"] for t in student["tests"]] == [soon["id"], later["id"]]
    assert [a["title"] for a in client.get("/api/assignments", headers=as_class(DEV, mine["id"])).json()] == ["דף עבודה"]
    assert [t["date"] for t in client.get("/api/home", headers=as_class(DEV, other["id"])).json()["tests"]] != [t["date"] for t in dev["tests"]]


def test_a_teacher_previews_only_the_classes_they_teach():
    client, mine, other, soon, later = world()
    assert [c["id"] for c in client.get("/api/me", headers=auth(TEACHER)).json()["preview"]] == [mine["id"]]
    assert len(client.get("/api/home", headers=as_class(TEACHER, mine["id"])).json()["tests"]) == 2
    assert client.get("/api/home", headers=as_class(TEACHER, other["id"])).json()["tests"] == []          # not theirs: nothing
    assert client.get("/api/assignments", headers=as_class(TEACHER, other["id"])).json() == []


def test_a_student_cannot_preview_another_class_and_keeps_their_own():
    client, mine, other, soon, later = world()
    assert client.get("/api/me", headers=auth(KID)).json()["preview"] == []
    tests = client.get("/api/home", headers=as_class(KID, other["id"])).json()["tests"]
    assert [t["id"] for t in tests] == [soon["id"], later["id"]]                                # the header changes nothing


@pytest.fixture
def browser():
    playwright = pytest.importorskip("playwright.sync_api")
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def test_in_the_browser_a_developer_picks_a_class_and_its_nearest_test_is_on_home(browser):
    client, mine, other, soon, later = world()
    with running(client.app) as url:
        page = offline_formulas(browser.new_page(viewport={"width": 390, "height": 844}))
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(url)
        page.fill("#email", DEV)
        page.click("#dev button")
        page.wait_for_selector("#nav .roles")
        page.click("#nav [data-role='student']")
        page.wait_for_selector("#view-as")
        page.click(".subject-card")
        page.wait_for_selector(".tabs")
        assert page.locator("#nearest-test").count() == 0                                         # no class: no test
        page.select_option("#view-class", str(mine["id"]))
        page.wait_for_selector("#nearest-test")
        assert "מחר" in page.inner_text("#nearest-test") and page.input_value("#view-class") == str(mine["id"])   # kept after the reload
        page.click("#nearest-test .strip-main")
        page.wait_for_selector("#other-tests")
        assert len(page.locator("#other-tests li").all()) == 1                                    # 28.12 under "מבחנים נוספים"
        page.select_option("#view-class", "")
        page.wait_for_selector("#view-as")
        assert errors == []
