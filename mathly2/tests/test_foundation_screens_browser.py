"""The foundation's screens in a real browser: the look, the sign-in page, the role switcher and each role's home."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import running

ADMIN, MGR, TEACHER, KID, DEV, BOTH = ("adm@school.test", "mgr@school.test", "t@school.test", "kid@school.test",
                                       "dev@school.test", "both@school.test")
PHONE, DESKTOP = {"width": 390, "height": 844}, {"width": 1280, "height": 800}


def seeded(**settings):
    store = InMemoryStore()
    store.give_role(ADMIN, "admin", "setup")
    store.give_role(MGR, "manager", "setup")
    store.give_role(BOTH, "manager", "setup")
    app = create_app(Settings(teachers=frozenset({TEACHER}), developers=frozenset({DEV}), **settings), store=store)
    return app, store


def sign_in(page, url, email):
    page.goto(url)
    page.fill("#email", email)
    page.click("#dev button")


def sign_out_and_in(page, email):
    page.click("#out")
    page.wait_for_selector("form#dev")
    page.fill("#email", email)
    page.click("#dev button")


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def page_for(browser, viewport):
    """A page that does not wait for the formula library from the network: these screens show no formulas."""
    page = browser.new_page(viewport=viewport)
    page.route("**/mathjax@*/**", lambda route: route.abort())
    return page


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


# --- 4.1 the sky look ---

def test_the_app_is_always_dark_with_stars_and_the_owl_stops_moving_under_reduced_motion(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        page.goto(url)
        page.wait_for_selector(".sky-owl")
        colors = {}
        for scheme in ("light", "dark"):                                     # a light device still gets the dark sky
            page.emulate_media(color_scheme=scheme)
            colors[scheme] = page.evaluate("getComputedStyle(document.body).backgroundColor")
        assert colors["light"] == colors["dark"] == "rgb(6, 10, 25)"
        image = page.evaluate("getComputedStyle(document.body).backgroundImage")
        assert image.count("radial-gradient") >= 10                         # two glows and the small stars
        page.emulate_media(reduced_motion="no-preference")
        assert page.evaluate("document.getAnimations().length") > 0          # the owl blinks: the test can see motion
        page.emulate_media(reduced_motion="reduce")
        assert page.evaluate("document.getAnimations().length") == 0


# --- 4.2 the sign-in page ---

def test_the_sign_in_page_has_the_logo_the_owl_a_status_line_and_the_dev_form(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        page.goto(url)
        page.wait_for_selector("#signin")
        assert page.get_attribute("#signin img.logo", "alt") == "לומדים בכיף" and page.locator("#signin .sky-owl").count() == 1
        assert page.evaluate("document.querySelector('#signin img.logo').complete && document.querySelector('#signin img.logo').naturalWidth") > 0
        assert "יש להיכנס" in page.inner_text("#signin .status") and "dev only" in page.inner_text("#signin")
        assert page.locator("#google").count() == 0
        no_sideways_scroll(page)


STUB = "window.supabase={createClient:()=>({auth:{getSession:async()=>({data:{session:null}}),signInWithOAuth:async()=>({}),signOut:async()=>({})}})}"


def with_supabase():
    store = InMemoryStore()
    settings = Settings(supabase_url="https://p.supabase.test", supabase_key="pub", supabase_secret="sec")
    return create_app(settings, store=store, authenticator=type("A", (), {"user": lambda self, t: None})())


def test_the_real_sign_in_page_has_one_google_button(browser):
    with running(with_supabase()) as url:
        page = page_for(browser, PHONE)
        page.route("**/supabase.js", lambda route: route.fulfill(content_type="text/javascript", body=STUB))
        page.goto(url)
        page.wait_for_selector("#google")
        assert page.inner_text("#google") == "כניסה עם Google" and page.locator("#signin button").count() == 1
        assert page.locator("form#dev").count() == 0


def test_when_the_sign_in_service_is_down_the_page_says_so_and_offers_to_try_again(browser):
    with running(with_supabase()) as url:
        page = page_for(browser, PHONE)
        page.route("**/supabase.js", lambda route: route.abort())
        page.goto(url)
        page.wait_for_selector("#retry")
        assert "לא הצלחנו להתחבר" in page.inner_text("#signin .status")
        page.unroute("**/supabase.js")
        page.route("**/supabase.js", lambda route: route.fulfill(content_type="text/javascript", body=STUB))
        page.click("#retry")
        page.wait_for_selector("#google")                                      # the retry worked


# --- 4.3 the role switcher ---

def test_a_manager_who_is_also_a_teacher_gets_two_chips_and_the_last_choice_is_remembered(browser):
    app, store = seeded()
    store.create_class("setup", "ט'3", lessons=["t"], teacher_email=BOTH)
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, BOTH)
        page.wait_for_selector("#nav .roles")
        assert [b.inner_text() for b in page.locator("#nav .roles button").all()] == ["מורה", "מנהל כיתות"]
        page.wait_for_selector("#teaching")                                    # the first role is the first one shown
        page.click("#nav [data-role='manager']")
        page.wait_for_selector("#mgr")
        assert page.get_attribute("#nav [data-role='manager']", "aria-pressed") == "true"
        page.reload()
        page.wait_for_selector("#mgr")                                         # remembered on this device
        page.click("#nav [data-role='teacher']")
        page.wait_for_selector("#teaching")


def test_a_person_with_one_role_sees_no_chips_and_a_developer_sees_all_five(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, TEACHER)
        page.wait_for_selector("#teaching")
        assert page.locator("#nav .roles").count() == 0
        sign_out_and_in(page, DEV)
        page.wait_for_selector("#nav .roles")
        assert page.locator("#nav .roles button").count() == 5


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_the_developer_screen_shows_the_system_status_version_and_update_date(browser, viewport):
    app, _ = seeded()
    app.state.version = {"commit": "c" * 40, "short": "ccccccc", "date": "2026-11-11T05:37:00+00:00", "source": "file"}
    with running(app) as url:
        page = page_for(browser, viewport)
        sign_in(page, url, DEV)
        page.wait_for_selector("#nav .roles")
        page.click("#nav [data-role='developer']")
        page.wait_for_selector("#st-checks li")
        assert page.get_attribute("#st-overall", "data-state") == "warn"                  # no Supabase here: memory only
        assert page.inner_text("#st-version") == "ccccccc"
        assert "2026" in page.inner_text("#st-updated") and "07:37" in page.inner_text("#st-updated")   # shown in Israel's time
        keys = [li.get_attribute("data-key") for li in page.locator("#st-checks li").all()]
        assert keys == ["database", "sign_in", "bank", "ai", "push", "pictures", "cleanup"]
        page.click("#st-refresh")
        page.wait_for_selector("#st-checks li")
        no_sideways_scroll(page)


# --- 4.4 the manager's screens ---

def fill_class(page, name, lessons, teacher, students):
    page.fill("#c-name", name)
    assert page.locator("#c-lessons, input[name=lesson]").count() == 0            # a class has no chosen lessons
    page.fill("#c-teacher", teacher)
    page.fill("#c-students", students)


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390px", "1280px"])
def test_a_manager_creates_edits_and_deletes_classes_without_scrolling_sideways(browser, viewport):
    app, store = seeded()
    with running(app) as url:
        page = page_for(browser, viewport)
        page.on("dialog", lambda d: d.accept())
        sign_in(page, url, MGR)
        page.wait_for_selector("#mgr")
        page.click("#new-class")
        page.wait_for_selector("#class-form")
        assert not page.is_checked("#c-ai") and page.input_value("#c-budget") == "150"        # the AI starts off
        fill_class(page, "ט'3", ["t", "t2"], "rina@school.test", "a@school.test\nb@school.test")
        page.click("#c-save")
        page.wait_for_selector("#classes article")
        assert "ט'3" in page.inner_text("#classes") and "rina@school.test" in page.inner_text("#classes") and "2 תלמידים" in page.inner_text("#classes")
        no_sideways_scroll(page)
        page.click("#new-class")
        fill_class(page, "ט'4", ["k"], "avi@school.test", "c@school.test")
        page.click("#c-save")
        page.wait_for_function("document.querySelectorAll('#classes article').length === 2")
        if viewport["width"] > 800:
            columns = page.evaluate("getComputedStyle(document.getElementById('classes')).gridTemplateColumns.split(' ').length")
            assert columns >= 2                                                 # the wide screen is used
        page.click("#classes article >> nth=0 >> [data-edit]")
        page.wait_for_selector("#class-form")
        assert page.input_value("#c-name") == "ט'3"
        page.fill("#c-name", "ט'3 חדשה")
        page.check("#c-ai")
        page.click("#c-save")
        page.wait_for_selector("#classes article")
        assert "ט'3 חדשה" in page.inner_text("#classes") and "AI: פועל" in page.inner_text("#classes")
        page.click("#classes article >> nth=0 >> [data-delete]")
        page.wait_for_function("document.querySelectorAll('#classes article').length === 1")
        assert [c["name"] for c in store.classes()] == ["ט'4"]
        page.click("[data-tab='students']")
        page.wait_for_selector("#students-list")
        assert "c@school.test" in page.inner_text("#students-list") and "ט'4" in page.inner_text("#students-list")
        no_sideways_scroll(page)


def test_the_editor_shows_why_a_class_was_not_saved(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, MGR)
        page.click("#new-class")
        fill_class(page, "ט'3", ["t"], "x@school.test", "x@school.test")
        page.click("#c-save")
        page.wait_for_selector("#mgr .error")
        assert "לא יכול להיות גם תלמיד" in page.inner_text("#mgr .error")


def test_a_refused_save_shows_the_reason_in_view_keeps_what_was_typed_and_can_then_be_fixed(browser):
    app, store = seeded()
    cid = store.create_class("setup", "ט'3", lessons=["t", "t2"], teacher_email="old@school.test")["id"]
    for email in ("a@school.test", "b@school.test"):
        store.add_member(cid, email)
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, DEV)                                                 # a developer manages classes too
        page.wait_for_selector("#nav .roles")
        page.click("#nav [data-role='manager']")
        page.click("[data-edit]")
        page.wait_for_selector("#class-form")
        page.fill("#c-name", "ט'3 חדשה")
        page.fill("#c-teacher", "a@school.test")                                # a student of the class: not allowed
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")         # the save button is at the bottom of a long form
        page.click("#c-save")
        page.wait_for_selector("#form-error")
        assert "לא נשמר" in page.inner_text("#form-error") and "לא יכול להיות גם תלמיד" in page.inner_text("#form-error")
        assert page.evaluate("(() => { const r = document.getElementById('form-error').getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; })()")
        assert page.input_value("#c-teacher") == "a@school.test" and page.input_value("#c-name") == "ט'3 חדשה"   # typed values stay
        assert store.get_class(cid)["teacher_email"] == "old@school.test"        # nothing was saved
        page.fill("#c-teacher", "newteacher@school.test")                        # fix the one thing
        page.click("#c-save")
        page.wait_for_selector("#classes article")
        saved = store.get_class(cid)
        assert (saved["teacher_email"], saved["name"]) == ("newteacher@school.test", "ט'3 חדשה")
        assert [m["email"] for m in store.members(cid)] == ["a@school.test", "b@school.test"]


# --- 4.5 the teacher's home ---

def test_a_teacher_adds_three_students_and_removes_one_and_has_no_class_editor(browser):
    app, store = seeded()
    store.create_class("setup", "ט'3", lessons=["t"], teacher_email=TEACHER)
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, TEACHER)
        page.wait_for_selector(".class-card")
        page.fill(".emails", "a@school.test, b@school.test\nc@school.test")
        page.click(".add-students button")
        page.wait_for_function("document.querySelectorAll('.students li').length === 3")
        assert "נוספו 3 תלמידים" in page.inner_text(".report")
        page.click("[data-remove='a@school.test']")
        page.wait_for_function("document.querySelectorAll('.students li').length === 2")
        page.fill(".emails", "t@school.test b@school.test")
        page.click(".add-students button")
        page.wait_for_function("document.querySelector('.report').innerText.includes('כבר היו בכיתה')")
        assert "מורה הכיתה לא יכול להיות גם תלמיד בה" in page.inner_text(".report")      # the teacher cannot add themselves
        assert page.locator("#mgr, #new-class, [data-edit], [data-delete]").count() == 0
        no_sideways_scroll(page)


def test_a_teacher_with_no_class_is_told_a_manager_chooses_the_teacher(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, TEACHER)
        page.wait_for_selector("#teaching")
        assert "מנהל הכיתות קובע" in page.inner_text("#teaching")


# --- 4.6 the admin's screen and the access page ---

def test_an_admin_gives_the_manager_role_to_a_new_email_and_the_last_admin_cannot_step_down(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, ADMIN)
        page.wait_for_selector("#accounts")
        page.fill("#g-email", "rina@school.test")
        page.select_option("#g-role", "manager")
        page.click("#give button")
        page.wait_for_selector("tr[data-email='rina@school.test']")
        assert "מנהל כיתות" in page.inner_text("tr[data-email='rina@school.test']")
        page.click(f"tr[data-email='{ADMIN}'] [data-take='admin']")
        page.wait_for_selector("#accounts .error")
        assert "האחרון" in page.inner_text("#accounts .error")
        no_sideways_scroll(page)


def test_every_account_can_see_its_own_roles_and_what_they_allow(browser):
    app, _ = seeded()
    with running(app) as url:
        page = page_for(browser, PHONE)
        sign_in(page, url, MGR)
        page.wait_for_selector("#mgr")
        page.click("#access")
        page.wait_for_selector("#my-access")
        text = page.inner_text("#my-access")
        assert MGR in text and "מנהל כיתות" in text and "ליצור, לערוך ולמחוק כיתות" in text and "בלי גישה לנתוני למידה" in text


# --- a link lands where it points, and changing role clears it ---

def test_a_link_and_a_reload_land_where_they_point_and_switching_role_clears_the_address(browser):
    app, store = seeded()
    store.add_member(store.create_class("setup", "ט'3", lessons=["t"], teacher_email=BOTH)["id"], KID)
    store.give_role(KID, "manager", "setup")                                      # two roles, so there is a switcher
    with running(app) as url:
        page = page_for(browser, PHONE)
        page.goto(url + "#/collection")
        page.fill("#email", KID)
        page.click("#dev button")
        page.wait_for_selector("#collection")                                      # the first screen honours the link
        page.reload()
        page.wait_for_selector("#collection")
        page.click("#nav [data-role='manager']")
        page.wait_for_selector("#mgr")
        assert page.evaluate("location.hash") == ""                                # switching role forgets the old address


# --- 6.1 the roles end to end ---

def test_an_admin_a_manager_a_teacher_and_a_student_each_do_their_part(browser):
    app, store = seeded()
    with running(app) as url:
        page = page_for(browser, DESKTOP)
        page.on("dialog", lambda d: d.accept())
        sign_in(page, url, ADMIN)
        page.wait_for_selector("#accounts")
        page.fill("#g-email", "newmgr@school.test")
        page.select_option("#g-role", "manager")
        page.click("#give button")
        page.wait_for_selector("tr[data-email='newmgr@school.test']")

        sign_out_and_in(page, "newmgr@school.test")
        page.wait_for_selector("#mgr")                                         # the role given before the first sign-in applies
        page.click("#new-class")
        fill_class(page, "ט'3", ["t", "t2"], TEACHER, "s1@school.test\ns2@school.test")
        page.click("#c-save")
        page.wait_for_selector("#classes article")

        sign_out_and_in(page, TEACHER)
        page.wait_for_selector(".class-card")
        assert page.locator(".students li").count() == 2
        page.fill(".emails", "s3@school.test")
        page.click(".add-students button")
        page.wait_for_function("document.querySelectorAll('.students li').length === 3")

        sign_out_and_in(page, "s3@school.test")
        page.click(".subject-card")                                           # a student of the class sees the subjects, then the home, then the path
        page.click(".tabs a[href='#/subject/math/path']")
        page.wait_for_selector("#path")
        assert [m["user_id"] is not None for m in store.members(store.classes()[0]["id"]) if m["email"] == "s3@school.test"] == [True]
        no_sideways_scroll(page)
