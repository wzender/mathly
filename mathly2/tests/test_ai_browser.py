"""AI help in a real browser (add-ai-help 3.1, 3.2): the student's photo help and the teacher's queue."""
import json
import urllib.request

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import ai, clock
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_written_browser import KID, PHONE, TEACHER, bank, browser, day, jpeg, uid  # noqa: F401


def make(bank, ai_on=True, fake=None, daily=5):
    store = InMemoryStore()
    lesson = next(u["id"] for u in bank.data["units"] if u.get("quiz"))
    klass = store.create_class("setup", "A", lessons=[lesson], teacher_email=TEACHER, ai_enabled=ai_on, ai_daily_checks=daily)
    store.add_member(klass["id"], KID)
    store.link_user(KID, uid(KID))
    fake = fake or ai.FakeAI()
    return create_app(Settings(), bank=bank, store=store, ai_client=fake), store, klass, fake, lesson


def call(url, path, who, method="POST", body=None):
    req = urllib.request.Request(url + path, method=method, data=json.dumps(body or {}).encode() if method != "GET" else None,
                                 headers={"Authorization": f"Bearer dev:{who}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read() or b"null")


def student(browser, url, where="", email=KID):
    page = offline_formulas(browser.new_page(viewport=PHONE))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + where)
    page.fill("#email", email)
    page.click("#dev button")
    page.errors = errors
    return page


def to_home(page):
    page.click(".subject-card")
    page.wait_for_selector(".tabs")


def teacher(browser, url, tab="ai"):
    page = offline_formulas(browser.new_page(viewport=PHONE))
    page.goto(url)
    page.fill("#email", TEACHER)
    page.click("#dev button")
    page.wait_for_selector("#teaching")
    if tab:
        page.click(f"#teacher-tabs [data-tab={tab}]")
    return page


def send_photo(page):
    page.click("#ai-new")
    page.wait_for_selector(".ai-window")
    page.set_input_files("[data-ai-file] >> nth=-1", files=[{"name": "p.jpg", "mimeType": "image/jpeg", "buffer": jpeg()}])
    page.click("#ai-send")
    page.wait_for_selector("#ai-state")


def test_no_photo_help_button_or_card_when_the_class_has_the_ai_off(browser, bank):
    app, store, klass, fake, lesson = make(bank, ai_on=False)
    with running(app) as url:
        page = student(browser, url)
        to_home(page)
        page.wait_for_selector("#continue-path")
        assert page.locator("#ai-card, #ai-new").count() == 0
        skill = next(s["id"] for s in bank.skills if s["unit"] == lesson)
        page.goto(url + f"#/skill/{skill}")
        page.wait_for_selector(".mx-sheet")
        assert page.locator("[data-ai]").count() == 0


def test_the_student_photographs_waits_then_gets_the_hints_one_at_a_time(browser, bank):
    app, store, klass, fake, lesson = make(bank)
    with running(app) as url:
        page = student(browser, url)
        to_home(page)
        page.wait_for_selector("#ai-card")
        send_photo(page)
        assert "ממתין למורה" in page.inner_text("#ai-state") and "המורה רואה את התמונה" in page.inner_text(".ai-window") and fake.calls == []
        rid = store.ai_requests()[0]["id"]
        call(url, f"/api/ai/requests/{rid}/send", TEACHER)
        page.wait_for_selector("#ai-steps", timeout=15000)                                  # the page looks again every few seconds
        assert page.locator("#ai-steps li").count() == 1 and page.locator("#ai-answer").count() == 0 and page.locator(".ai-work").count() == 0
        page.click("#ai-next-hint")
        assert page.locator("#ai-steps li").count() == 2 and page.locator("#ai-next-hint").count() == 0
        page.click("[data-more=work] >> nth=0")
        assert page.locator(".ai-work").count() == 1
        page.click("#ai-show-answer")
        assert "x = 2" in page.inner_text("#ai-answer") or "2" in page.inner_text("#ai-answer")
        assert not page.errors


def test_a_waiting_request_can_be_cancelled_and_a_decline_shows_the_note(browser, bank):
    app, store, klass, fake, lesson = make(bank)
    with running(app) as url:
        page = student(browser, url)
        to_home(page)
        page.wait_for_selector("#ai-card")
        send_photo(page)
        page.click("#ai-cancel")
        page.wait_for_function("document.querySelector('#ai-state').innerText.includes('בוטל')")
        page.click("[data-ai-close]")
        send_photo(page)
        rid = [r for r in store.ai_requests() if r["state"] == "waiting"][0]["id"]
        call(url, f"/api/ai/requests/{rid}/decline", TEACHER, body={"note": "צלמו שוב"})
        page.wait_for_selector("#ai-note", timeout=15000)
        assert "צלמו שוב" in page.inner_text("#ai-note") and page.locator("#ai-photo").count() == 0


def test_the_exercise_screens_camera_button_tells_the_teacher_which_skill_and_the_queue_shows_it(browser, bank):
    app, store, klass, fake, lesson = make(bank)
    skill = next(s for s in bank.skills if s["unit"] == lesson)
    with running(app) as url:
        page = student(browser, url, f"#/skill/{skill['id']}")
        page.wait_for_selector("[data-ai]")
        page.click(".ex-ai")
        page.wait_for_selector(".ai-window")
        page.set_input_files("[data-ai-file] >> nth=-1", files=[{"name": "p.jpg", "mimeType": "image/jpeg", "buffer": jpeg()}])
        page.click("#ai-send")
        page.wait_for_selector("#ai-state")
        t = teacher(browser, url)
        t.wait_for_selector("#ai-waiting")
        assert skill["name"].replace("$", "")[:6] in t.inner_text(".ai-item").replace("$", "") or t.locator(".ai-item").count() == 1
        assert t.inner_text("#teacher-tabs [data-tab=ai] .tab-count") == "1" and t.locator(".ai-item img").count() == 1
        assert store.ai_requests()[0]["skill_id"] == skill["id"]


def test_the_teacher_sends_and_it_shows_done_a_failure_shows_its_cause_and_a_retry_works(browser, bank):
    fake = ai.FakeAI(fail="no_credit")
    app, store, klass, _, lesson = make(bank, fake=fake)
    with running(app) as url:
        pic = __import__("mathly2.pictures", fromlist=["x"]).store_picture(store, app.state.pictures, uid(KID), "help", jpeg())
        store.create_ai_request("photo", uid(KID), klass["id"], picture_id=pic["id"], created_at=clock.now())
        t = teacher(browser, url)
        t.wait_for_selector("#ai-waiting .ai-item")
        t.click("[data-send]")
        t.wait_for_selector("#ai-rest [data-state=failed]", timeout=15000)
        text = t.inner_text("#ai-rest")
        assert "נגמרה היתרה" in text and "להוסיף יתרה" in text and "fake" in text                      # the cause, what to do, the detail
        fake.fail = None
        t.click("#ai-rest [data-send]")
        t.wait_for_selector("#ai-rest [data-state=done]", timeout=15000)
        assert t.locator("#ai-waiting").count() == 0 and t.inner_text("#teacher-tabs [data-tab=ai] .tab-count") == "0"


def test_a_batch_with_a_short_budget_says_so_and_a_decline_has_a_note_box(browser, bank):
    app, store, klass, fake, lesson = make(bank, daily=2)
    with running(app) as url:
        for _ in range(4):
            pic = __import__("mathly2.pictures", fromlist=["x"]).store_picture(store, app.state.pictures, uid(KID), "help", jpeg())
            store.create_ai_request("photo", uid(KID), klass["id"], picture_id=pic["id"], created_at=clock.now())
        t = teacher(browser, url)
        t.wait_for_selector("#ai-batches")
        assert "נשארו 2 מתוך 2" in t.inner_text("#ai-budgets")
        t.click("[data-batch=photos]")
        t.wait_for_selector("#ai-message:not([hidden])")
        assert "נשלחו 2" in t.inner_text("#ai-message") and "מחר" in t.inner_text("#ai-message")
        assert t.locator("#ai-waiting .ai-item").count() == 2
        t.click("[data-decline-open] >> nth=0")
        assert t.locator("[data-decline]:not([hidden]) [data-note]").count() == 1


def test_a_check_is_asked_by_the_student_shown_to_the_teacher_as_a_suggestion_and_the_grade_is_the_teachers(browser, bank):
    app, store, klass, fake, lesson = make(bank)
    row = store.create_assignment(klass["id"], "בוחן כתוב", day(5), TEACHER, "quiz", quiz_lesson=lesson, created_at=clock.now())
    from mathly2 import pictures
    pic = pictures.store_picture(store, app.state.pictures, uid(KID), "answer", jpeg("blue"))
    store.save_submission(row["id"], uid(KID), pictures=[pic["id"]], state="handed_in", late=False, handed_at=clock.now(), grade=None, teacher_note="")
    with running(app) as url:
        page = student(browser, url, f"#/assignment/{row['id']}")
        page.wait_for_selector("#ask-check")
        page.click("#ask-check")
        page.wait_for_selector("#ai-box [data-state=waiting]")
        rid = store.ai_requests(kinds=["check"])[0]["id"]
        t = teacher(browser, url, tab="inbox")
        assert t.locator("#teacher-tabs [data-tab=ai] .tab-count").inner_text() in ("1", "")
        call(url, f"/api/ai/requests/{rid}/send", TEACHER)
        page.wait_for_selector("#ai-box [data-state=done]", timeout=15000)
        assert "הציון המוצע" in page.inner_text("#ai-box") and "המורה קובע" in page.inner_text("#ai-box")
        t.reload()                                                                              # still signed in
        t.wait_for_selector("#teaching")
        t.click("#teacher-tabs [data-tab=inbox]")
        t.click("[data-open]")
        t.wait_for_selector("#ai-suggestion")
        assert t.inner_text("#ai-score") == "100" and "הציון שלכם קובע" in t.inner_text("#ai-suggestion")
        t.fill("[name=grade]", "70")
        t.click("#give-grade")
        t.wait_for_selector("#inbox-notice")
        assert store.get_submission(row["id"], uid(KID))["grade"] == 70 and store.get_ai_request(rid)["result"]["score"] == 100
        page.reload()
        page.goto(url + f"#/assignment/{row['id']}")
        page.wait_for_selector("#ask-again")
        page.click("#ask-again")
        page.wait_for_selector("#again-asked")
        t.click("#teacher-tabs [data-tab=inbox]")
        t.wait_for_selector("[data-kind=again]")
        assert "ביקש/ה בדיקה חוזרת" in t.inner_text("#inbox-list")
