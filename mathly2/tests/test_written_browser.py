"""Written work in a real browser: the student's assignments, handing in, photo requests, notifications, and the teacher's side
(add-written-work 3.x and 4.x)."""
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from PIL import Image

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, running

TEACHER, KID, KID2 = "t@school.test", "kid@school.test", "kid2@school.test"
PHONE = {"width": 360, "height": 800}
DESKTOP = {"width": 1280, "height": 800}


def uid(email):
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, email))


def jpeg(color="red", size=(120, 80)):
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, "JPEG")
    return out.getvalue()


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def world(bank, **settings):
    lessons = [u["id"] for u in bank.data["units"] if u.get("quiz")]
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=lessons[:2], teacher_email=TEACHER)
    for email in (KID, KID2):
        store.add_member(klass["id"], email)
        store.link_user(email, uid(email))
    app = create_app(Settings(**settings), bank=bank, store=store)
    return app, store, klass, lessons


def day(n):
    return (clock.school_day() + timedelta(days=n))


def sign_in(browser, url, email=KID, where="", viewport=PHONE, **context):
    page = offline_formulas(browser.new_page(viewport=viewport, **context))
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


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


# --- 3.1 my assignments on home ---

def seeded_assignments(bank):
    app, store, klass, lessons = world(bank)
    quiz = lambda title, n: store.create_assignment(klass["id"], title, day(n), TEACHER, "quiz", quiz_lesson=lessons[0])
    rows = {"fresh": quiz("חדש", 5), "handed": quiz("הוגש", 6), "graded": quiz("נבדק", 1), "returned": quiz("הוחזר", 7), "late": quiz("מאחר", -2)}
    store.save_submission(rows["handed"]["id"], uid(KID), pictures=["p"])
    store.save_submission(rows["graded"]["id"], uid(KID), pictures=["p"], state="graded", grade=85, teacher_note="יפה")
    store.save_submission(rows["returned"]["id"], uid(KID), pictures=["p"], state="returned", teacher_note="תקנו")
    test = store.create_test(klass["id"], day(10), lessons[:1], TEACHER, created_at=clock.now())
    rows["exam"] = store.create_assignment(klass["id"], "מבחן תרגול", day(4), TEACHER, "exercise_test", test_id=test["id"], exercise_number=1)
    rows["test"] = test
    return app, store, rows


def test_home_lists_only_the_new_assignments_with_due_date_and_state_in_words(browser, bank):
    app, store, rows = seeded_assignments(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#assignments")
        listed = lambda a: page.locator(f"#assignments li[data-assignment='{a['id']}']")
        assert "לא הוגש" in listed(rows["fresh"]).inner_text() and f"{day(5).day}.{day(5).month}" in listed(rows["fresh"]).inner_text()
        assert "באיחור" in listed(rows["late"]).inner_text() and "עוד לא נעשה" in listed(rows["exam"]).inner_text()
        assert page.get_attribute(f"#assignments li[data-assignment='{rows['fresh']['id']}'] a", "href") == f"#/assignment/{rows['fresh']['id']}"
        assert page.get_attribute(f"#assignments li[data-assignment='{rows['exam']['id']}'] a", "href") == f"#/exam/{rows['test']['id']}/1"   # an exercise test opens the test
        assert page.locator("#assignments li b").all_inner_texts() == ["מאחר", "מבחן תרגול", "חדש"]                                       # only the new ones, by due date
        for hidden in ("handed", "graded", "returned"):
            assert listed(rows[hidden]).count() == 0                                                                                   # the rest are in "הגשות"
        no_sideways_scroll(page)
        assert page.errors == []


def test_the_submissions_tab_lists_every_assignment_grouped_by_state(browser, bank):
    app, store, rows = seeded_assignments(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.click(".tabs a[href='#/submissions']")
        page.wait_for_selector("#submissions")
        groups = {g.get_attribute("data-group"): g for g in page.locator("#submissions .group").all()}
        assert list(groups) == ["new", "returned", "waiting", "checked"]                                                              # what to do first, then what waits, then done
        titles = lambda name: groups[name].locator("li b").all_inner_texts()
        assert titles("new") == ["מאחר", "מבחן תרגול", "חדש"] and titles("returned") == ["הוחזר"] and titles("waiting") == ["הוגש"] and titles("checked") == ["נבדק"]
        assert "תקנו" in groups["returned"].inner_text() and "ציון 85" in groups["checked"].inner_text() and "יפה" in groups["checked"].inner_text()
        assert "באיחור" in groups["new"].locator("li", has_text="מאחר").inner_text() and "הוחזר לתיקון" in groups["returned"].inner_text()
        assert sum(g.locator("li").count() for g in groups.values()) == 6                                                              # every assignment from the teacher
        assert page.locator(".tabs a[aria-current='page']").inner_text() == "הגשות"
        page.click("#submissions li[data-state='returned'] a")                                                                        # each opens its page
        page.wait_for_selector("#returned")
        assert page.locator(".tabs a[aria-current='page']").inner_text() == "הגשות"
        no_sideways_scroll(page)


def test_a_student_with_no_assignments_sees_none_on_either_screen(browser, bank):
    app, _, _, _ = world(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        assert page.locator("#assignments").count() == 0
        page.click(".tabs a[href='#/submissions']")
        page.wait_for_selector("#no-assignments")


def test_home_has_no_assignments_card_when_there_are_none(browser, bank):
    app, _, _, _ = world(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        assert page.locator("#assignments").count() == 0


# --- 3.2 the assignment page ---

def draw_on_board(page):
    box = page.locator(".mx-board canvas").bounding_box()
    page.mouse.move(box["x"] + 40, box["y"] + 60)
    page.mouse.down()
    page.mouse.move(box["x"] + 160, box["y"] + 120, steps=8)
    page.mouse.up()


def upload(page, color="red", name="answer.jpg"):
    page.set_input_files("[data-file=upload]", files=[{"name": name, "mimeType": "image/jpeg", "buffer": jpeg(color)}])


def one_assignment(bank, kind="quiz", title="דף עבודה", days=5):
    app, store, klass, lessons = world(bank)
    if kind == "pages":
        pic = store.create_picture(TEACHER, "page", "t/p1.jpg", "image/jpeg", 100)
        app.state.pictures.put("t/p1.jpg", jpeg("blue", (300, 200)))
        row = store.create_assignment(klass["id"], title, day(days), TEACHER, "pages", note="לפתור את כל התרגילים", pages=[pic["id"]])
    else:
        row = store.create_assignment(klass["id"], title, day(days), TEACHER, "quiz", quiz_lesson=lessons[0])
    return app, store, row


def test_the_page_shows_the_note_the_pages_and_the_bank_quiz(browser, bank):
    app, store, row = one_assignment(bank, "pages")
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#assignment")
        assert "לפתור את כל התרגילים" in page.inner_text("#assignment-note") and "לא הוגש" in page.inner_text("#state")
        page.wait_for_function("document.querySelector('#pages img').naturalWidth > 0")                    # the page picture came through the server
        no_sideways_scroll(page)
    app2, _, quiz = one_assignment(bank, "quiz")
    with running(app2) as url:
        page = sign_in(browser, url, where=f"#/assignment/{quiz['id']}")
        page.wait_for_selector("#written-quiz")
        assert page.locator("#written-quiz li").count() == 4 and "100 נקודות" in page.inner_text("#material")


def test_a_photo_from_a_file_joins_the_answer_and_handing_in_shows_it_as_handed_in(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#answer")
        assert page.is_disabled("#hand-in") and page.locator("#add-actions [data-file=camera]").count() == 0           # a desktop: no camera button
        upload(page)
        upload(page, "green")
        page.wait_for_selector("#draft li[data-picture-id] img:not([hidden])")
        assert page.locator("#draft li[data-picture-id]").count() == 2 and not page.is_disabled("#hand-in")
        page.click("#draft li[data-picture-id] .remove >> nth=0")                                               # a picture can be taken out
        assert page.locator("#draft li[data-picture-id]").count() == 1
        page.click("#hand-in")
        page.wait_for_selector("#assignment[data-state='handed_in']")
        sub = store.get_submission(row["id"], uid(KID))
        assert sub["state"] == "handed_in" and len(sub["pictures"]) == 1 and "ההגשה נשלחה" in page.inner_text("#hand-msg")
        assert page.inner_text("#hand-in") == "החלפת ההגשה"                                                       # until checked, it can be replaced
        assert page.errors == []


def test_the_phone_gets_a_camera_button_and_a_photo_from_it_joins_the_answer(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}", has_touch=True, is_mobile=True)
        page.wait_for_selector("#answer")
        assert page.locator("[data-file=camera]").get_attribute("capture") == "environment"
        page.set_input_files("[data-file=camera]", files=[{"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": jpeg("orange", (3000, 2000))}])
        page.wait_for_selector("#draft li[data-picture-id]")
        pid = page.get_attribute("#draft li[data-picture-id]", "data-picture-id")
        size = store.get_picture(pid)["size"]
        assert size < 400_000 and store.get_picture(pid)["kind"] == "answer"                                    # shrunk on the device before it was sent


def test_a_stroke_on_the_board_is_added_to_the_answer_by_the_send_button(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}", viewport=DESKTOP)
        page.wait_for_selector("#board-btn")
        page.click("#board-btn")
        page.wait_for_selector(".mx-board canvas")
        draw_on_board(page)
        page.click(".mx-board-send")
        page.click(".mx-board-back")
        page.wait_for_selector("#draft li[data-picture-id]")
        pid = page.get_attribute("#draft li[data-picture-id]", "data-picture-id")
        assert store.get_picture(pid)["kind"] == "answer" and not page.is_disabled("#hand-in")


def test_a_returned_assignment_shows_the_note_and_can_be_handed_in_again_but_a_graded_one_cannot_be_changed(browser, bank):
    app, store, row = one_assignment(bank)
    pic = store.create_picture(uid(KID), "answer", f"{uid(KID)}/old.jpg", "image/jpeg", 100)
    app.state.pictures.put(pic["path"], jpeg())
    store.save_submission(row["id"], uid(KID), pictures=[pic["id"]], state="returned", teacher_note="חסר נימוק בסעיף 2")
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#returned")
        assert "חסר נימוק בסעיף 2" in page.inner_text("#returned") and "הוחזר לתיקון" in page.inner_text("#state")
        assert page.locator("#draft li[data-picture-id]").count() == 1                                          # the earlier picture is still there to fix
        upload(page, "purple")
        page.wait_for_function("document.querySelectorAll('#draft li[data-picture-id]').length === 2")
        page.click("#hand-in")
        page.wait_for_selector("#assignment[data-state='handed_in']")
        assert store.get_submission(row["id"], uid(KID))["state"] == "handed_in" and len(store.get_submission(row["id"], uid(KID))["pictures"]) == 2
        store.save_submission(row["id"], uid(KID), state="graded", grade=91, teacher_note="יפה מאוד")
        page.reload()
        page.wait_for_selector("#grade")
        assert page.inner_text("#grade b") == "91" and "יפה מאוד" in page.inner_text("#teacher-note")
        assert page.locator("#hand-in").count() == 0 and page.locator("#add-actions").count() == 0              # a graded one is not changed
        page.wait_for_function("document.querySelector('#submitted img')?.naturalWidth > 0")


def test_pictures_that_were_deleted_say_so(browser, bank):
    app, store, row = one_assignment(bank)
    pic = store.create_picture(uid(KID), "answer", "x/gone.jpg", "image/jpeg", 100)
    store.mark_picture_deleted(pic["id"])
    store.save_submission(row["id"], uid(KID), pictures=[pic["id"]], state="graded", grade=80)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#answer")
        assert "התמונות נמחקו" in page.inner_text("#submitted") and page.inner_text("#grade b") == "80"


def test_an_exercise_test_assignment_page_links_to_the_test_and_has_no_answer_box(browser, bank):
    app, store, klass, lessons = world(bank)
    test = store.create_test(klass["id"], day(10), lessons[:1], TEACHER, created_at=clock.now())
    row = store.create_assignment(klass["id"], "תרגול", day(3), TEACHER, "exercise_test", test_id=test["id"], exercise_number=2)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        page.wait_for_selector("#assignment")
        assert page.get_attribute("#material a", "href") == f"#/exam/{test['id']}/2" and page.locator("#answer").count() == 0


# --- 3.3 the photo request: the computer and the phone ---

FAST = "window.__photoPollComputer = 200; window.__photoPollPhone = 200;"


def two_devices(browser, url, assignment_id):
    """The same student on a computer and on a phone (two browsers: each has its own device id)."""
    computer = browser.new_context(viewport=DESKTOP)
    phone = browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
    pages = []
    for ctx in (computer, phone):
        ctx.add_init_script(FAST)
        page = offline_formulas(ctx.new_page())
        page.goto(url)
        page.fill("#email", KID)
        page.click("#dev button")
        pages.append(page)
    comp, ph = pages
    comp.goto(f"{url}#/assignment/{assignment_id}")
    comp.wait_for_selector("#ask-phone")
    ph.wait_for_selector(".subject-card")
    return comp, ph


def test_the_phone_shows_the_same_code_and_a_photo_from_it_reaches_the_computers_answer(browser, bank):
    app, store, row = one_assignment(bank)
    app.state.photo_code = lambda: 4821
    with running(app) as url:
        comp, ph = two_devices(browser, url, row["id"])
        comp.click("#ask-phone")
        comp.wait_for_selector("#request-code")
        assert comp.inner_text("#request-code") == "4821" and "ממתינים לטלפון" in comp.inner_text("#request-state")
        ph.wait_for_selector("#photo-window")
        assert ph.inner_text("#phone-code") == "4821" and "דף עבודה" in ph.inner_text("#photo-window")
        assert ph.locator("[data-photo]").get_attribute("capture") == "environment"
        ph.set_input_files("[data-photo]", files=[{"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": jpeg("teal", (2400, 1600))}])
        ph.wait_for_function("document.getElementById('phone-state')?.innerText.includes('נשלחה')")
        comp.wait_for_function("document.getElementById('request-state')?.innerText.includes('התשובה התקבלה')")
        comp.wait_for_selector("#draft li[data-picture-id] img:not([hidden])")                              # the photo joined the answer on the computer
        assert comp.locator("#draft li[data-picture-id]").count() == 1 and not comp.is_disabled("#hand-in")
        ph.wait_for_selector("#photo-window", state="detached")
        assert store.pictures()[0]["kind"] == "answer"


def test_the_computer_that_asked_never_shows_its_own_request_window(browser, bank):
    app, _, row = one_assignment(bank)
    with running(app) as url:
        page = sign_in(browser, url, where=f"#/assignment/{row['id']}", viewport=DESKTOP)
        page.add_init_script(FAST)
        page.wait_for_selector("#ask-phone")
        page.evaluate("window.__photoPollPhone = 200")
        page.click("#ask-phone")
        page.wait_for_selector("#request-code")
        page.goto(url + "#/subject/math")
        page.reload()
        page.wait_for_selector(".tabs")
        page.wait_for_timeout(1500)
        assert page.locator("#photo-window").count() == 0


def test_a_newer_request_marks_the_older_one_replaced_and_not_now_closes_the_window_for_good(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        comp, ph = two_devices(browser, url, row["id"])
        comp.click("#ask-phone")
        comp.wait_for_selector("#request-code")
        first = comp.inner_text("#request-code")
        comp.click("#ask-phone")
        comp.wait_for_function("document.querySelector('.old-requests')?.innerText.includes('הוחלפה')")
        assert first in comp.inner_text(".old-requests")
        states = sorted(r["state"] for r in [store.get_photo_request(r["id"]) for r in store.open_photo_requests(uid(KID))] if r)
        assert states == ["waiting"]                                                                          # only the newer one is open
        ph.wait_for_selector("#photo-window")
        ph.click("#phone-later")
        ph.wait_for_selector("#photo-window", state="detached")
        ph.wait_for_timeout(1000)
        assert ph.locator("#photo-window").count() == 0                                                      # it does not come back


def test_a_request_that_expires_closes_the_phones_window_and_the_computer_says_so(browser, bank):
    app, store, row = one_assignment(bank)
    with running(app) as url:
        comp, ph = two_devices(browser, url, row["id"])
        comp.click("#ask-phone")
        comp.wait_for_selector("#request-code")
        ph.wait_for_selector("#photo-window")
        pending = store.open_photo_requests(uid(KID))[0]
        store.save_photo_request(pending["id"], state="expired")
        ph.wait_for_selector("#photo-window", state="detached")
        comp.wait_for_function("document.getElementById('request-state')?.innerText.includes('פגה')")


# --- 3.4 notifications on the phone ---

FAKE_PUSH = """
(() => {
  const sub = { endpoint: "https://push.test/phone-1", toJSON() { return { endpoint: this.endpoint, keys: { p256dh: "pp", auth: "aa" } }; },
                async unsubscribe() { window.__unsubscribed = true; return true; } };
  let current = null, listeners = [];
  const registration = { pushManager: { async getSubscription() { return current; },
                                         async subscribe(options) { window.__subscribeOptions = options; current = sub; return sub; } } };
  Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: {
    async register(url, options) { window.__registered = [url, options && options.scope]; return registration; },
    addEventListener(type, fn) { if (type === "message") window.__swMessage = fn; }, removeEventListener() {} } });
  window.PushManager = window.PushManager || function () {};
  window.Notification = { requestPermission: async () => "granted", permission: "default" };
})();
"""


def phone_context(browser, with_push=True, touch=True):
    ctx = browser.new_context(viewport=PHONE, has_touch=touch, is_mobile=touch)
    if with_push:
        ctx.add_init_script(FAKE_PUSH)
    return ctx


def phone_home(ctx, url):
    page = offline_formulas(ctx.new_page())
    page.goto(url)
    page.fill("#email", KID)
    page.click("#dev button")
    to_home(page)
    assert page.locator("#notifications").count() == 0                                                  # not on home
    page.click(".tabs a[href='#/submissions']")
    page.wait_for_selector("#submissions")
    return page


def test_the_switch_is_only_on_a_touch_device_and_only_when_the_server_has_a_key(browser, bank):
    from mathly2 import push
    key = push.new_private_key()
    app_on, _, _, _ = world(bank, vapid_private_key=key)
    with running(app_on) as url:
        on = phone_home(phone_context(browser), url)
        on.wait_for_selector("#notif-on")                                                                  # a phone, a key: offered
        assert on.evaluate("window.__registered") == ["/service-worker.js", "/"]
        desktop = phone_home(phone_context(browser, touch=False), url)
        desktop.wait_for_timeout(800)
        assert desktop.locator("#notifications:not([hidden])").count() == 0                                # a computer: not offered
    app_off, _, _, _ = world(bank)
    with running(app_off) as url:
        off = phone_home(phone_context(browser), url)
        off.wait_for_timeout(800)
        assert off.locator("#notifications:not([hidden])").count() == 0                                    # no key on the server: not offered


def test_turning_notifications_on_sends_the_subscription_and_turning_them_off_removes_it(browser, bank):
    from mathly2 import push
    key = push.new_private_key()
    app, store, _, _ = world(bank, vapid_private_key=key)
    with running(app) as url:
        page = phone_home(phone_context(browser), url)
        page.click("#notif-on")
        page.wait_for_selector("#notif-state")
        assert "פועלות" in page.inner_text("#notif-state")
        subs = store.push_subscriptions_of(uid(KID))
        assert [s["endpoint"] for s in subs] == ["https://push.test/phone-1"] and subs[0]["p256dh"] == "pp" and subs[0]["key_id"]
        assert page.evaluate("window.__subscribeOptions.userVisibleOnly") is True and page.evaluate("window.__subscribeOptions.applicationServerKey.length") == 65   # the server's key
        page.click("#notif-off")
        page.wait_for_selector("#notif-on")
        assert page.evaluate("window.__unsubscribed") is True and store.push_subscriptions_of(uid(KID)) == []


def test_a_tapped_notification_makes_the_open_app_look_for_requests_at_once(browser, bank):
    from mathly2 import push
    app, store, _, _ = world(bank, vapid_private_key=push.new_private_key())
    row = store.create_assignment(store.classes()[0]["id"], "דף", day(5), TEACHER, "quiz", quiz_lesson=[u["id"] for u in bank.data["units"] if u.get("quiz")][0])
    with running(app) as url:
        ctx = phone_context(browser)
        ctx.add_init_script("window.__photoPollPhone = 600000;")                                          # no timer: only the notification can make it look
        page = phone_home(ctx, url)
        page.wait_for_selector("#notif-on")
        page.wait_for_timeout(300)
        assert page.locator("#photo-window").count() == 0
        now = clock.now()
        store.create_photo_request(uid(KID), row["id"], "some-laptop", "7777", now, now + timedelta(minutes=10))
        page.evaluate("window.__swMessage({ data: { type: 'notified' } })")                                # the service worker says a notification was tapped
        page.wait_for_selector("#photo-window")
        assert page.inner_text("#phone-code") == "7777"


# --- 3.5 the grades screen ---

def test_graded_assignments_and_done_exercise_tests_appear_on_the_grades_screen_with_the_teachers_note(browser, bank):
    app, store, klass, lessons = world(bank)
    graded = store.create_assignment(klass["id"], "בוחן כתוב", day(-3), TEACHER, "quiz", quiz_lesson=lessons[0])
    removed = store.create_assignment(klass["id"], "דף שהוסר", day(-6), TEACHER, "quiz", quiz_lesson=lessons[0])
    waiting = store.create_assignment(klass["id"], "עוד לא נבדק", day(2), TEACHER, "quiz", quiz_lesson=lessons[0])
    store.save_submission(graded["id"], uid(KID), pictures=["p"], state="graded", grade=92, teacher_note="נימוק יפה")
    store.save_submission(removed["id"], uid(KID), pictures=["p"], state="graded", grade=70)
    store.save_submission(waiting["id"], uid(KID), pictures=["p"])
    store.remove_assignment(removed["id"])
    test = store.create_test(klass["id"], day(10), lessons[:1], TEACHER, created_at=clock.now())
    exam = store.create_assignment(klass["id"], "תרגול 1", day(4), TEACHER, "exercise_test", test_id=test["id"], exercise_number=1)
    attempt = store.create_attempt(uid(KID), "exercise_test", f"{test['id']}:1", clock.now() - timedelta(hours=2), clock.now() + timedelta(hours=1), [])
    store.save_attempt(attempt["id"], submitted_at=clock.now(), grade=77)
    with running(app) as url:
        page = sign_in(browser, url, where="#/grades")
        page.wait_for_selector("#assignment-grades")
        row = lambda a: page.locator(f"#assignment-grades li[data-assignment='{a['id']}']")
        assert row(graded).locator(".gr-num").inner_text() == "92" and "נימוק יפה" in row(graded).inner_text()
        assert row(exam).locator(".gr-num").inner_text() == "77" and "מבחן תרגול" in row(exam).inner_text()
        assert "הוסרה" in row(removed).inner_text() and row(removed).locator(".gr-num").inner_text() == "70"       # a removed assignment keeps its grade
        assert row(waiting).count() == 0 and page.locator("#no-grades").count() == 0                             # not graded yet: not a grade
        assert row(graded).locator("a").get_attribute("href") == f"#/assignment/{graded['id']}"
        no_sideways_scroll(page)


# --- 4.1 the teacher's assignments tab ---

def make_pdf(pages):
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument.new()
    for _ in range(pages):
        doc.new_page(200, 300)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def teacher_work(browser, url, viewport=PHONE, tab="assignments", **context):
    page = offline_formulas(browser.new_page(viewport=viewport, **context))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.fill("#email", TEACHER)
    page.click("#dev button")
    page.wait_for_selector("#teaching")
    page.click(f"#teacher-tabs [data-tab='{tab}']")
    page.wait_for_selector("#work, #inbox")
    page.errors = errors
    return page


def fill_basics(page, title="משימה חדשה", days=6):
    page.click(".new-assignment summary")
    page.fill("[name=title]", title)
    page.fill("[name=due_date]", day(days).isoformat())


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_a_teacher_gives_the_banks_written_quiz_to_the_class(browser, bank, viewport):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = teacher_work(browser, url, viewport)
        assert "עוד לא נתנו משימה" in page.inner_text(".class-work")
        fill_basics(page, "בוחן כתוב לשיעור")
        page.check("[name=source][value=quiz]")
        page.select_option("[name=quiz_lesson]", lessons[0])
        page.click(".assignment-form button[type=submit]")
        page.wait_for_selector(".assignment-row")
        row = page.locator(".assignment-row")
        assert "בוחן כתוב" in row.inner_text() and "0 מתוך 2 הגישו" in row.inner_text() and "בוחן כתוב לשיעור" in row.inner_text()
        assert store.assignments_of_classes([klass["id"]])[0]["quiz_lesson"] == lessons[0]
        no_sideways_scroll(page)
        assert page.errors == []


def test_a_teacher_gives_pages_from_an_image_a_pdf_and_a_photo(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = teacher_work(browser, url, PHONE, has_touch=True, is_mobile=True)
        fill_basics(page, "דף מהמחשב ומהמצלמה")
        assert page.locator("[data-pages-camera]").get_attribute("capture") == "environment"                    # a phone: the camera is offered
        page.set_input_files("[data-pages-file]", files=[{"name": "a.jpg", "mimeType": "image/jpeg", "buffer": jpeg("red")}])
        page.wait_for_selector("[data-pages] li[data-page]")
        page.set_input_files("[data-pages-file]", files=[{"name": "sheets.pdf", "mimeType": "application/pdf", "buffer": make_pdf(3)}])
        page.wait_for_function("document.querySelectorAll('[data-pages] li[data-page]').length === 4")          # one image + a PDF of three pages
        page.set_input_files("[data-pages-camera]", files=[{"name": "photo.jpg", "mimeType": "image/jpeg", "buffer": jpeg("green", (2400, 1600))}])
        page.wait_for_function("document.querySelectorAll('[data-pages] li[data-page]').length === 5")
        page.click("[data-pages] li[data-page] .remove >> nth=0")
        assert page.locator("[data-pages] li[data-page]").count() == 4
        page.click(".assignment-form button[type=submit]")
        page.wait_for_selector(".assignment-row")
        made = store.assignments_of_classes([klass["id"]])[0]
        assert made["kind"] == "pages" and len(made["pages"]) == 4 and "4 עמודים" in page.inner_text(".assignment-row")
        assert all(store.get_picture(p)["kind"] == "page" for p in made["pages"])


def test_a_teacher_writes_the_assignment_on_the_board(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = teacher_work(browser, url, DESKTOP)
        fill_basics(page, "נכתב על הלוח")
        page.click("[data-pages-board]")
        page.wait_for_selector(".mx-board canvas")
        draw_on_board(page)
        page.click(".mx-board-send")
        page.click(".mx-board-back")
        page.wait_for_selector("[data-pages] li[data-page]")
        page.click(".assignment-form button[type=submit]")
        page.wait_for_selector(".assignment-row")
        assert store.assignments_of_classes([klass["id"]])[0]["kind"] == "pages" and "1 עמודים" in page.inner_text(".assignment-row")


def test_a_teacher_sends_an_exercise_test_and_sees_how_many_did_it(browser, bank):
    app, store, klass, lessons = world(bank)
    test = store.create_test(klass["id"], day(10), lessons[:1], TEACHER, created_at=clock.now())
    with running(app) as url:
        page = teacher_work(browser, url)
        fill_basics(page, "תרגול לכיתה")
        page.check("[name=source][value=exercise_test]")
        page.select_option("[name=exercise_number]", "2")
        page.click(".assignment-form button[type=submit]")
        page.wait_for_selector(".assignment-row")
        made = store.assignments_of_classes([klass["id"]])[0]
        assert (made["kind"], made["test_id"], made["exercise_number"]) == ("exercise_test", test["id"], 2) and "0 מתוך 2 עשו" in page.inner_text(".assignment-row")


def test_the_form_keeps_what_was_typed_when_the_server_refuses_and_removing_takes_two_steps(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = teacher_work(browser, url)
        fill_basics(page, "בלי עמודים")
        page.fill("[name=note]", "לא לאבד את זה")
        page.click(".assignment-form button[type=submit]")                                                        # pages chosen, none added: refused
        page.wait_for_selector(".assignment-form .form-error:not([hidden])")
        assert page.input_value("[name=note]") == "לא לאבד את זה" and page.input_value("[name=title]") == "בלי עמודים" and store.assignments_of_classes([klass["id"]]) == []
        page.check("[name=source][value=quiz]")
        page.click(".assignment-form button[type=submit]")
        page.wait_for_selector(".assignment-row")
        sub_row = store.assignments_of_classes([klass["id"]])[0]
        store.save_submission(sub_row["id"], uid(KID), pictures=["p"])
        store.save_submission(sub_row["id"], uid(KID2), pictures=["p"], state="graded", grade=80)
        page.reload()
        page.click("#teacher-tabs [data-tab='assignments']")
        page.wait_for_selector(".assignment-row")
        assert "2 מתוך 2 הגישו" in page.inner_text(".assignment-row") and "1 נבדקו" in page.inner_text(".assignment-row") and "1 מחכות לבדיקה" in page.inner_text(".assignment-row")
        page.click("[data-remove-assignment]")
        page.click("[data-confirm-remove-assignment]")
        page.wait_for_selector(".assignment-row", state="detached")
        assert store.assignments_of_classes([klass["id"]]) == [] and store.get_submission(sub_row["id"], uid(KID2))["grade"] == 80


# --- 4.2 the inbox ---

def two_submissions(bank, **settings):
    app, store, klass, lessons = world(bank, **settings)
    row = store.create_assignment(klass["id"], "בוחן כתוב", day(5), TEACHER, "quiz", quiz_lesson=lessons[0])
    made = []
    for email, offset, color in ((KID2, 1, "blue"), (KID, 0, "red")):                      # KID2's hand-in is Tuesday, KID's is Monday (made second)
        pic = store.create_picture(uid(email), "answer", f"{uid(email)}/a.jpg", "image/jpeg", 100)
        app.state.pictures.put(pic["path"], jpeg(color))
        made.append(store.save_submission(row["id"], uid(email), pictures=[pic["id"]], handed_at=datetime(2026, 11, 9 + offset, 10, 0, tzinfo=timezone.utc)))
    return app, store, row, made


def test_the_inbox_lists_oldest_first_and_a_grade_empties_its_item(browser, bank):
    app, store, row, (tuesday, monday) = two_submissions(bank)
    with running(app) as url:
        page = teacher_work(browser, url, PHONE, tab="inbox")
        page.wait_for_selector("#inbox-list")
        items = page.locator("#inbox-list li")
        assert items.count() == 2 and KID in items.nth(0).inner_text() and KID2 in items.nth(1).inner_text()      # Monday's first
        page.click(f"[data-open='{monday['id']}']")
        page.wait_for_selector("#check")
        page.wait_for_function("document.querySelector('#answer-pictures img')?.naturalWidth > 0")               # the teacher sees the picture
        page.fill("[name=grade]", "88")
        page.fill("[name=note]", "נימוק יפה")
        page.click("#give-grade")
        page.wait_for_selector("#inbox-notice")
        assert "הציון נשמר" in page.inner_text("#inbox-notice") and page.locator("#inbox-list li").count() == 1 and KID2 in page.inner_text("#inbox-list")
        saved = store.get_submission(row["id"], uid(KID))
        assert (saved["state"], saved["grade"], saved["teacher_note"], saved["checked_by"]) == ("graded", 88, "נימוק יפה", TEACHER)
        no_sideways_scroll(page)
        assert page.errors == []


def test_sending_back_needs_a_note_and_a_grade_must_be_a_whole_number_from_0_to_100(browser, bank):
    app, store, row, (tuesday, monday) = two_submissions(bank)
    with running(app) as url:
        page = teacher_work(browser, url, DESKTOP, tab="inbox")
        page.click(f"[data-open='{tuesday['id']}']")
        page.wait_for_selector("#check")
        page.click("#send-back")
        assert "צריך לכתוב מה לתקן" in page.inner_text("#check-error") and store.get_submission(row["id"], uid(KID2))["state"] == "handed_in"
        for bad in ("", "101", "-3", "8.5"):
            page.fill("[name=grade]", bad)
            page.click("#give-grade")
            assert "מספר שלם" in page.inner_text("#check-error"), bad
        page.fill("[name=note]", "חסר נימוק בסעיף 2")
        page.click("#send-back")
        page.wait_for_selector("#inbox-notice")
        assert "הוחזרה" in page.inner_text("#inbox-notice") and page.locator("#inbox-list li").count() == 1             # a returned one leaves the inbox
        sent = store.get_submission(row["id"], uid(KID2))
        assert (sent["state"], sent["teacher_note"]) == ("returned", "חסר נימוק בסעיף 2")


def test_a_submission_the_student_replaced_meanwhile_says_so_and_reopens(browser, bank):
    app, store, row, (tuesday, monday) = two_submissions(bank)
    with running(app) as url:
        page = teacher_work(browser, url, PHONE, tab="inbox")
        page.click(f"[data-open='{monday['id']}']")
        page.wait_for_selector("#check")
        store.save_submission(row["id"], uid(KID), handed_at=datetime(2026, 11, 11, 9, 0, tzinfo=timezone.utc))            # the student handed in again
        page.fill("[name=grade]", "70")
        page.click("#give-grade")
        page.wait_for_selector("#check-error:not([hidden])")
        assert "השתנתה" in page.inner_text("#check-error") and store.get_submission(row["id"], uid(KID))["state"] == "handed_in"
        page.click("#reopen")
        page.wait_for_selector("#inbox-list")


def test_an_empty_inbox_says_everything_was_checked_and_the_student_then_sees_the_result(browser, bank):
    app, store, row, (tuesday, monday) = two_submissions(bank)
    with running(app) as url:
        teacher = teacher_work(browser, url, PHONE, tab="inbox")
        for sub_row, grade in ((monday, 90), (tuesday, 60)):
            teacher.click(f"[data-open='{sub_row['id']}']")
            teacher.fill("[name=grade]", str(grade))
            teacher.click("#give-grade")
            teacher.wait_for_selector("#inbox-notice")
        assert "אין מה לבדוק" in teacher.inner_text("#inbox-empty")
        student = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        student.wait_for_selector("#grade")
        assert student.inner_text("#grade b") == "90"


def test_a_teacher_deletes_a_students_pictures_from_the_class_screen_and_the_grade_stays(browser, bank):
    app, store, row, (tuesday, monday) = two_submissions(bank)
    store.save_submission(row["id"], uid(KID), state="graded", grade=88, teacher_note="יפה")
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url)
        page.fill("#email", TEACHER)
        page.click("#dev button")
        page.wait_for_selector("#teaching")
        page.click(f"[data-wipe='{KID}']")
        page.click("[data-confirm-wipe]")                                                              # two steps
        page.wait_for_function("document.querySelector('.report')?.innerText.includes('נמחקו 1 תמונות')")
        assert "הציונים וההערות נשארו" in page.inner_text(".report")
        assert all(store.get_picture(p)["deleted_at"] for p in monday["pictures"]) and not any(store.get_picture(p)["deleted_at"] for p in tuesday["pictures"])
        assert store.get_submission(row["id"], uid(KID))["grade"] == 88
        student = sign_in(browser, url, where=f"#/assignment/{row['id']}")
        student.wait_for_selector("#grade")
        assert "התמונות נמחקו" in student.inner_text("#submitted") and student.inner_text("#grade b") == "88"


# --- 5.1 the whole flow ---

def test_the_whole_written_work_flow_from_the_teachers_assignment_to_the_grades(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        # the teacher gives an assignment from a file, and one from the bank's written quiz
        teacher = teacher_work(browser, url, DESKTOP)
        fill_basics(teacher, "דף מהקובץ")
        teacher.set_input_files("[data-pages-file]", files=[{"name": "sheet.jpg", "mimeType": "image/jpeg", "buffer": jpeg("blue", (300, 200))}])
        teacher.wait_for_selector("[data-pages] li[data-page]")
        teacher.click(".assignment-form button[type=submit]")
        teacher.wait_for_selector(".assignment-row")
        teacher.click(".new-assignment summary")
        teacher.fill(".new-assignment [name=title]", "בוחן כתוב")
        teacher.fill(".new-assignment [name=due_date]", day(6).isoformat())
        teacher.check(".new-assignment [name=source][value=quiz]")
        teacher.click(".assignment-form button[type=submit]")
        teacher.wait_for_function("document.querySelectorAll('.assignment-row').length === 2")
        sheet = next(a for a in store.assignments_of_classes([klass["id"]]) if a["title"] == "דף מהקובץ")

        # the first student hands in from the board
        first = sign_in(browser, url, KID, f"#/assignment/{sheet['id']}", DESKTOP)
        first.wait_for_selector("#board-btn")
        first.wait_for_function("document.querySelector('#pages img')?.naturalWidth > 0")
        first.click("#board-btn")
        first.wait_for_selector(".mx-board canvas")
        draw_on_board(first)
        first.click(".mx-board-send")
        first.click(".mx-board-back")
        first.wait_for_selector("#draft li[data-picture-id]")
        first.click("#hand-in")
        first.wait_for_selector("#assignment[data-state='handed_in']")

        # the second student asks their phone for a photo from the computer
        ctx_computer, ctx_phone = browser.new_context(viewport=DESKTOP), browser.new_context(viewport=PHONE, has_touch=True, is_mobile=True)
        pages = []
        for ctx in (ctx_computer, ctx_phone):
            ctx.add_init_script(FAST)
            page = offline_formulas(ctx.new_page())
            page.goto(url)
            page.fill("#email", KID2)
            page.click("#dev button")
            pages.append(page)
        computer, phone = pages
        computer.goto(f"{url}#/assignment/{sheet['id']}")
        computer.wait_for_selector("#ask-phone")
        computer.click("#ask-phone")
        phone.wait_for_selector("#photo-window")
        phone.set_input_files("[data-photo]", files=[{"name": "p.jpg", "mimeType": "image/jpeg", "buffer": jpeg("orange", (1200, 800))}])
        computer.wait_for_selector("#draft li[data-picture-id]")
        computer.click("#hand-in")
        computer.wait_for_selector("#assignment[data-state='handed_in']")

        # the teacher's inbox shows both, the first student's first; one is graded and one is sent back
        teacher.click("#teacher-tabs [data-tab='inbox']")
        teacher.wait_for_selector("#inbox-list")
        items = teacher.locator("#inbox-list li")
        assert items.count() == 2 and KID in items.nth(0).inner_text() and KID2 in items.nth(1).inner_text()
        items.nth(0).locator("button").click()
        teacher.wait_for_function("document.querySelector('#answer-pictures img')?.naturalWidth > 0")
        teacher.fill("[name=grade]", "90")
        teacher.fill("[name=note]", "מצוין")
        teacher.click("#give-grade")
        teacher.wait_for_selector("#inbox-notice")
        teacher.locator("#inbox-list li button").click()
        teacher.fill("[name=note]", "חסר נימוק בסעיף 2")
        teacher.click("#send-back")
        teacher.wait_for_selector("#inbox-empty")

        # the second student sees why it came back, hands in again, and is graded
        computer.reload()
        computer.wait_for_selector("#returned")
        assert "חסר נימוק בסעיף 2" in computer.inner_text("#returned")
        computer.set_input_files("[data-file=upload]", files=[{"name": "fix.jpg", "mimeType": "image/jpeg", "buffer": jpeg("purple")}])
        computer.wait_for_function("document.querySelectorAll('#draft li[data-picture-id]').length === 2")
        computer.click("#hand-in")
        computer.wait_for_selector("#assignment[data-state='handed_in']")
        teacher.click("#teacher-tabs [data-tab='inbox']")
        teacher.wait_for_selector("#inbox-list")
        teacher.locator("#inbox-list li button").click()
        teacher.fill("[name=grade]", "75")
        teacher.click("#give-grade")
        teacher.wait_for_selector("#inbox-empty")

        # both grades are on the grades screens
        for page, grade in ((first, "90"), (computer, "75")):
            page.goto(f"{url}#/grades")
            page.wait_for_selector("#assignment-grades")
            assert page.locator("#assignment-grades .gr-num").inner_text() == grade

        # the teacher deletes the first student's pictures; the grade stays
        teacher.click("#teacher-tabs [data-tab='classes']")
        teacher.click(f"[data-wipe='{KID}']")
        teacher.click("[data-confirm-wipe]")
        teacher.wait_for_function("document.querySelector('.report')?.innerText.includes('נמחקו')")
        first.goto(f"{url}#/assignment/{sheet['id']}")
        first.wait_for_selector("#grade")
        assert "התמונות נמחקו" in first.inner_text("#submitted") and first.inner_text("#grade b") == "90"
        assert store.get_submission(sheet["id"], uid(KID2))["grade"] == 75 and any(not store.get_picture(p)["deleted_at"] for p in store.get_submission(sheet["id"], uid(KID2))["pictures"])


# --- work-tabs-and-hints 2.1: the numbers on the teacher's tabs ---

def test_every_teacher_tab_shows_its_number_and_the_numbers_change_after_grading(browser, bank):
    app, store, row, (tuesday, monday) = two_submissions(bank)
    klass = store.classes()[0]
    lessons = klass["lessons"]
    for n in (10, 12, 14):
        store.create_test(klass["id"], day(n), lessons[:1], TEACHER, created_at=clock.now())
    store.create_assignment(klass["id"], "עוד אחת", day(4), TEACHER, "quiz", quiz_lesson=lessons[0])
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url)
        page.fill("#email", TEACHER)
        page.click("#dev button")
        page.wait_for_selector("#teaching")
        page.wait_for_function("document.querySelector('[data-count=inbox]')?.innerText !== ''")
        numbers = lambda: {el.get_attribute("data-count"): el.inner_text() for el in page.locator("#teacher-tabs [data-count]").all()}
        assert numbers() == {"classes": "1", "tests": "3", "assignments": "2", "inbox": "2", "progress": "2"}
        for tab in ("tests", "assignments", "inbox"):                                                     # on every tab
            page.click(f"#teacher-tabs [data-tab='{tab}']")
            page.wait_for_function("(t) => document.querySelector(`#teacher-tabs [data-tab='${t}'][aria-pressed='true']`) && [...document.querySelectorAll('#teacher-tabs [data-count]')].every(e => e.innerText !== '')", arg=tab)
            assert numbers() == {"classes": "1", "tests": "3", "assignments": "2", "inbox": "2", "progress": "2"}, tab
        page.click(f"[data-open='{monday['id']}']")
        page.fill("[name=grade]", "80")
        page.click("#give-grade")
        page.wait_for_selector("#inbox-notice")
        page.wait_for_function("document.querySelector('[data-count=inbox]')?.innerText === '1'")           # grading lowered the inbox number
        assert "הכיתות שלי 1" in page.inner_text("#teacher-tabs").replace("\n", " ")
        no_sideways_scroll(page)


def test_the_teachers_class_screen_fits_a_phone_with_students_and_their_buttons(browser, bank):
    app, store, klass, lessons = world(bank)
    store.add_member(klass["id"], "a-student-with-a-quite-long-address@school.example.test")
    with running(app) as url:
        page = offline_formulas(browser.new_page(viewport=PHONE))
        page.goto(url)
        page.fill("#email", TEACHER)
        page.click("#dev button")
        page.wait_for_selector(".students li")
        page.wait_for_function("document.querySelector('[data-count=classes]')?.innerText !== ''")
        no_sideways_scroll(page)
        for tab in ("tests", "assignments", "inbox"):
            page.click(f"#teacher-tabs [data-tab='{tab}']")
            page.wait_for_selector("#tests, #work, #inbox")
            no_sideways_scroll(page)
