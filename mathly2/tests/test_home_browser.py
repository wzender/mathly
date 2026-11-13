"""The student's home, the bottom tab bar and a test's card in a real browser (add-test-readiness 3.1-3.3, 3.5)."""
import uuid
from collections import Counter
from datetime import timedelta

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.bank import load_bank
from mathly2.config import Settings
from mathly2.main import create_app
from mathly2.store import InMemoryStore
from mathly2.tests.serve import offline_formulas, only, running

KID, TEACHER = "kid@school.test", "t@school.test"
KID_ID = str(uuid.uuid5(uuid.NAMESPACE_DNS, KID))
PHONE = {"width": 360, "height": 800}
PATH_TAB = ".tabs a[href='#/subject/math/path']"


@pytest.fixture(scope="module")
def bank():
    return load_bank()


@pytest.fixture
def browser():
    with playwright.sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def world(bank):
    sizes = Counter(s["unit"] for s in bank.skills if bank.question_keys(s["id"]))
    lessons = [l for l, c in sizes.items() if c == 4][:2]
    store = InMemoryStore()
    klass = store.create_class("setup", "A", lessons=lessons, teacher_email=TEACHER)
    store.add_member(klass["id"], KID)
    return create_app(Settings(), bank=only(bank, lessons), store=store), store, klass, lessons


def add_test(store, klass, lessons, days_ahead, set_days_ago=20, **kw):
    """A test `days_ahead` days from today that was set `set_days_ago` days ago (so the full plan applies)."""
    now = clock.now()
    return store.create_test(klass["id"], clock.school_day() + timedelta(days=days_ahead), lessons, TEACHER,
                             created_at=now - timedelta(days=set_days_ago), **kw)


def covered(bank, lessons):
    return [s["id"] for s in bank.skills if s["unit"] in lessons and bank.question_keys(s["id"])]


def sign_in(browser, url, where="", viewport=PHONE):
    page = offline_formulas(browser.new_page(viewport=viewport))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + where)
    page.fill("#email", KID)
    page.click("#dev button")
    page.errors = errors
    return page


def to_home(page):
    page.click(".subject-card")
    page.wait_for_selector(".tabs")


def no_sideways_scroll(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


# --- 3.1 the card opens home and the tab bar is at the bottom ---

def test_the_card_opens_home_and_each_tab_opens_its_screen(browser, bank):
    app, _, _, _ = world(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        assert page.evaluate("location.hash") == "#/subject/math" and page.locator(".tabs a[aria-current='page']").inner_text() == "בית"
        assert page.locator(".tabs a").all_inner_texts() == ["בית", "העמקה", "הגשות", "ציונים", "האוסף", "חזרה"]
        for href, marker in (("#/subject/math/path", ".orbit"), ("#/submissions", "#submissions"), ("#/grades", "#grades"), ("#/collection", "#collection"), ("#/review", "#review"), ("#/subject/math", "#lesson-map")):
            page.click(f".tabs a[href='{href}']")
            page.wait_for_selector(marker)
        assert page.errors == []


def test_the_tab_bar_stays_at_the_bottom_with_big_targets_and_covers_nothing(browser, bank):
    app, _, _, _ = world(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.click(PATH_TAB)
        page.wait_for_selector(".orbit")
        bar = page.locator(".tabs").bounding_box()
        assert abs(bar["y"] + bar["height"] - PHONE["height"]) <= 1 and bar["width"] == PHONE["width"]
        for box in [t.bounding_box() for t in page.locator(".tabs a").all()]:
            assert box["height"] >= 44 and box["width"] >= 44
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        last = page.evaluate("document.querySelector('.trail').lastElementChild.getBoundingClientRect().bottom")
        assert last <= page.locator(".tabs").bounding_box()["y"] + 1                                      # the end of the page is above the bar
        no_sideways_scroll(page)


def test_a_link_to_a_skill_still_opens_the_path_with_its_sheet(browser, bank):
    app, _, _, lessons = world(bank)
    skill = covered(bank, lessons)[0]
    with running(app) as url:
        page = sign_in(browser, url, f"#/skill/{skill}")
        page.wait_for_selector(".mx-sheet #ex-q")
        assert page.locator("#path").count() == 1 and page.locator(".tabs").count() == 1
        page.click(".mx-x")
        page.wait_for_selector(".orbit")
        assert page.evaluate("location.hash") == "#/subject/math/path"


# --- 3.2 home ---

def test_with_no_test_home_shows_the_map_and_a_link_to_the_path(browser, bank):
    app, _, _, lessons = world(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#lesson-map")
        assert page.locator("#nearest-test").count() == 0
        assert page.get_attribute("#continue-path", "href") == "#/subject/math/path"
        assert page.get_attribute("#play", "href") == f"#/round/{lessons[0]}"
        no_sideways_scroll(page)


def test_nine_days_before_the_test_the_button_opens_exercise_test_1_with_the_readiness_bar(browser, bank):
    app, store, klass, lessons = world(bank)
    skills = covered(bank, lessons)
    for i in skills[:6]:
        store.save_progress(KID_ID, i, started_at="then", mastered_at="then")                            # M = 6 of 8
    test = add_test(store, klass, lessons, 9)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        assert "בעוד 9 ימים" in page.inner_text("#nearest-test h2")
        assert page.get_attribute("#today-task", "href") == f"#/exam/{test['id']}/1" and "מבחן תרגול 1" in page.inner_text("#today-task")
        bar = page.locator("#nearest-test [role=progressbar]")
        assert bar.get_attribute("aria-valuenow") == "75" and "75" in bar.get_attribute("aria-label")
        part = lambda p: page.locator(f".rd-part[data-part={p}]")
        assert part("M").inner_text().split() == ["שליטה", "אחוז", "המיומנויות", "שנשלטו", "75%"]
        assert "מבחני תרגול" in part("E").inner_text() and "ממוצע הציונים הטובים ביותר" in part("E").inner_text() and part("E").locator(".rd-val").inner_text() == "—"
        assert "סימולציה" in part("S").inner_text() and "הציון במבחן הסימולציה" in part("S").inner_text() and part("S").locator(".rd-val").inner_text() == "—"
        assert not any(f" {letter} " in f" {page.inner_text('.rd-parts')} " for letter in "MES")                 # no letters
        assert "עוד לא עשיתם מבחן סימולציה" in page.inner_text(".rd-note")
        no_sideways_scroll(page)


def test_four_days_before_the_test_the_simulation_is_required_on_home(browser, bank):
    app, store, klass, lessons = world(bank)
    test = add_test(store, klass, lessons, 4)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        required = page.locator(f".required[data-required='{test['id']}']")
        assert required.count() == 1 and "חובה" in required.inner_text() and required.get_attribute("href") == f"#/sim/{test['id']}"
        assert page.get_attribute("#today-task", "href") == f"#/sim/{test['id']}"


def test_the_readiness_bar_shows_every_part_and_loses_the_cap_after_the_simulation(browser, bank):
    app, store, klass, lessons = world(bank)
    for i in covered(bank, lessons):
        store.save_progress(KID_ID, i, started_at="then", mastered_at="then")
    test = add_test(store, klass, lessons, 3)
    now = clock.now()
    for scope, kind, grade in ((f"{test['id']}:1", "exercise_test", 60), (f"{test['id']}:2", "exercise_test", 80), (str(test["id"]), "simulation", 90)):
        row = store.create_attempt(KID_ID, kind, scope, now - timedelta(days=1), now - timedelta(days=1) + timedelta(minutes=45), [])
        store.save_attempt(row["id"], submitted_at=now - timedelta(days=1) + timedelta(minutes=5), grade=grade)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        vals = {p: page.locator(f".rd-part[data-part={p}] .rd-val").inner_text() for p in "MES"}
        assert vals == {"M": "100%", "E": "70", "S": "90"}
        assert page.locator(".rd-note").count() == 0 and "מוכנים" in page.inner_text(".rd-label")
        assert page.locator(".required").count() == 0                                                     # the simulation is taken


def test_home_shows_only_the_closest_test_and_the_other_tests_are_on_its_card(browser, bank):
    app, store, klass, lessons = world(bank)
    far = add_test(store, klass, lessons, 20)
    near = add_test(store, klass, lessons, 9)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        assert page.get_attribute("#nearest-test", "data-test") == str(near["id"]) and page.get_attribute("#today-task", "href") == f"#/exam/{near['id']}/1"
        assert page.locator("#other-tests").count() == 0 and page.locator("#notifications").count() == 0                       # only what is critical
        page.click("#nearest-test a[href^='#/test/']")
        page.wait_for_selector("#other-tests")
        assert page.get_attribute("#other-tests a", "href") == f"#/test/{far['id']}"


# --- 3.3 a test's card ---

def card_page(browser, url, test_id):
    page = sign_in(browser, url, f"#/test/{test_id}")
    page.wait_for_selector("#test-card")
    return page


def finished(store, scope, kind, grade, questions=None, answers=None):
    now = clock.now()
    row = store.create_attempt(KID_ID, kind, scope, now - timedelta(days=1), now - timedelta(days=1) + timedelta(minutes=45), questions or [])
    return store.save_attempt(row["id"], submitted_at=now - timedelta(days=1) + timedelta(minutes=9), grade=grade, answers=answers or {})


def test_a_fresh_card_shows_the_plan_the_exercise_tests_what_to_practise_first_and_when_the_simulation_opens(browser, bank):
    app, store, klass, lessons = world(bank)
    skills = covered(bank, lessons)
    store.save_progress(KID_ID, skills[0], started_at="then", mastered_at="then")
    test = add_test(store, klass, lessons, 14, questions=10, minutes=30)
    with running(app) as url:
        page = card_page(browser, url, test["id"])
        assert "10 שאלות · 30 דקות" in page.inner_text("#test-card") and "בעוד 14 ימים" in page.inner_text("#test-card h2")
        steps = page.locator("#plan li")
        assert steps.count() == 5 and [steps.nth(i).get_attribute("data-step") for i in range(5)] == ["path", "ex1", "ex2", "sim", "review"]
        assert "עד 9 ימים לפני" in steps.nth(0).inner_text() and "בערך 9 ימים לפני" in steps.nth(1).inner_text() and "בערך 5 ימים לפני" in steps.nth(3).inner_text()
        assert page.locator("#plan li.done").count() == 0
        assert page.locator("#exercises li").count() == 2 and "עוד לא נעשה" in page.inner_text("#exercises li >> nth=0")
        assert page.get_attribute("#exercises li[data-exercise='2'] a", "href") == f"#/exam/{test['id']}/2" and "התחלה" in page.inner_text("#exercises li >> nth=1")
        assert page.locator("#practice-first a").count() == 7                                           # eight covered skills, one started
        assert "ייפתח ב־" in page.inner_text("#sim-closed") and page.locator("#sim-start").count() == 0
        no_sideways_scroll(page)


def test_exercise_tests_show_their_best_grade_and_offer_a_retake_or_to_continue(browser, bank):
    app, store, klass, lessons = world(bank)
    test = add_test(store, klass, lessons, 10)
    finished(store, f"{test['id']}:1", "exercise_test", 55)
    finished(store, f"{test['id']}:1", "exercise_test", 80)
    now = clock.now()
    store.create_attempt(KID_ID, "exercise_test", f"{test['id']}:2", now, now + timedelta(minutes=45), [])        # exercise test 2 is open
    with running(app) as url:
        page = card_page(browser, url, test["id"])
        one, two = page.locator("#exercises li[data-exercise='1']"), page.locator("#exercises li[data-exercise='2']")
        assert "הציון הטוב: 80" in one.inner_text() and "2 ניסיונות" in one.inner_text() and "שוב" in one.locator("a").inner_text()
        assert "להמשיך" in two.locator("a").inner_text()
        assert page.locator("#plan li[data-step='ex1'].done").count() == 1 and page.locator("#plan li[data-step='ex2'].done").count() == 0


def test_an_open_simulation_is_required_and_a_taken_one_shows_its_grade_and_review_skills(browser, bank):
    app, store, klass, lessons = world(bank)
    skills = covered(bank, lessons)
    test = add_test(store, klass, lessons, 4)
    with running(app) as url:
        page = card_page(browser, url, test["id"])
        assert page.locator("#simulation .req").count() == 1 and page.get_attribute("#sim-start", "href") == f"#/sim/{test['id']}"
        assert "התחלה" in page.inner_text("#sim-start")
        questions = [{"skill_id": skills[0], "key": bank.question_keys(skills[0])[0]}, {"skill_id": skills[1], "key": bank.question_keys(skills[1])[0]}]
        finished(store, str(test["id"]), "simulation", 0, questions=questions)                          # nothing answered: both skills failed
        page.reload()
        page.wait_for_selector("#simulation[data-taken='true']")
        assert page.inner_text("#sim-grade") == "0" and page.locator("#sim-start").count() == 0
        assert [a.get_attribute("href") for a in page.locator("#sim-review a").all()] == [f"#/skill/{skills[0]}", f"#/skill/{skills[1]}"]
        assert page.locator("#plan li[data-step='sim'].done").count() == 1


def test_a_test_of_another_class_or_a_missing_one_shows_an_error(browser, bank):
    app, _, _, _ = world(bank)
    with running(app) as url:
        page = sign_in(browser, url, "#/test/999")
        page.wait_for_selector("[role=alert]")
        assert "לא נמצא" in page.inner_text("[role=alert]")


# --- 3.4 the same sheet runs exercise tests and the simulation ---

def started_skills(store, bank, lessons, n=5):
    skills = covered(bank, lessons)
    for i in skills[:n]:
        store.save_progress(KID_ID, i, started_at="then")
    return skills


def test_an_exercise_test_runs_with_the_tests_length_and_no_timer_and_links_its_weak_skills_at_the_end(browser, bank):
    app, store, klass, lessons = world(bank)
    skills = started_skills(store, bank, lessons)
    test = add_test(store, klass, lessons, 10, questions=6, minutes=30)
    with running(app) as url:
        page = sign_in(browser, url, f"#/exam/{test['id']}/1")
        page.wait_for_selector("#qz-q")
        assert page.evaluate("location.hash").startswith(f"#/exam/{test['id']}/1/")                         # the address names the attempt
        assert "מבחן תרגול 1" in page.inner_text(".mx-sheet") and page.locator(".qz-dot").count() == 6
        assert page.locator("#qz-timer").count() == 0                                                         # only the simulation is timed
        sheet = page.inner_text(".mx-sheet")
        assert not any(bank.skill(i)["name"] in sheet for i in skills)                                       # no skill names, no feedback
        page.click("#qz-submit")
        page.click("#qz-yes")
        page.wait_for_selector("#qz-grade")
        assert page.inner_text("#qz-grade b") == "0" and "תוצאת מבחן תרגול 1" in page.inner_text(".mx-sheet")
        links = [a.get_attribute("href") for a in page.locator("#qz-lost a").all()]
        assert links and all(h.startswith("#/skill/") and h[8:] in skills for h in links)                    # weak skills link to their stars
        assert page.locator("#qz-retake").inner_text() == "מבחן חוזר"
        page.click("#qz-retake")                                                                             # a retake is a new attempt
        page.wait_for_selector("#qz-q")
        assert len(store.attempts_of(KID_ID, "exercise_test", f"{test['id']}:1")) == 2
        page.click(".mx-x")
        page.wait_for_selector("#test-card")                                                                 # closing leads back to the test's card
        assert page.evaluate("location.hash") == f"#/test/{test['id']}"


def test_the_simulation_can_be_taken_once_and_a_second_visit_shows_the_result(browser, bank):
    app, store, klass, lessons = world(bank)
    started_skills(store, bank, lessons)
    test = add_test(store, klass, lessons, 4, questions=6, minutes=45)
    with running(app) as url:
        page = sign_in(browser, url, f"#/sim/{test['id']}")
        page.wait_for_selector("#qz-q")
        assert "מבחן סימולציה" in page.inner_text(".mx-sheet") and page.locator(".qz-dot").count() == 6
        assert page.inner_text("#qz-timer").startswith("44:") or page.inner_text("#qz-timer") == "45:00"        # the test's minutes
        page.click("#qz-submit")
        page.click("#qz-yes")
        page.wait_for_selector("#qz-grade")
        assert page.locator("#qz-retake").count() == 0 and "פעם אחת" in page.inner_text(".qz-result")
        page.goto(url + f"#/sim/{test['id']}")                                                               # opening it again
        page.reload()
        page.wait_for_selector("#qz-grade")
        assert page.inner_text("#qz-grade b") == "0" and page.locator("#qz-q").count() == 0
        assert len(store.attempts_of(KID_ID, "simulation")) == 1
        page.click(".qz-actions [data-close]")
        page.wait_for_selector("#test-card")
        assert page.inner_text("#sim-grade") == "0"


def test_when_the_simulations_countdown_reaches_zero_it_is_handed_in_as_it_stands(browser, bank):
    from mathly2 import quiz
    app, store, klass, lessons = world(bank)
    started_skills(store, bank, lessons)
    test = add_test(store, klass, lessons, 4, questions=6, minutes=45)
    drawn = quiz.draw(bank, lessons[0])[:5]
    with running(app) as url:
        page = sign_in(browser, url)                                                                         # signed in before the clock starts
        now = clock.now()
        row = store.create_attempt(KID_ID, "simulation", str(test["id"]), now - timedelta(minutes=45) + timedelta(seconds=8),
                                   now + timedelta(seconds=8), drawn)
        page.goto(url + f"#/sim/{test['id']}/{row['id']}")
        page.wait_for_selector("#qz-timer")
        page.wait_for_selector("#qz-grade", timeout=25000)
        assert page.inner_text("#qz-grade b") == "0" and "הזמן נגמר" in page.inner_text(".qz-result")


def test_the_simulation_before_its_window_says_when_it_opens_and_does_not_start(browser, bank):
    app, store, klass, lessons = world(bank)
    started_skills(store, bank, lessons)
    test = add_test(store, klass, lessons, 14)
    with running(app) as url:
        page = sign_in(browser, url, f"#/sim/{test['id']}")
        page.wait_for_selector("[role=alert]")
        assert "ייפתח" in page.inner_text("[role=alert]") and page.locator("#qz-q").count() == 0
        assert store.attempts_of(KID_ID, "simulation") == []


# --- 3.5 the grades screen has exercise tests and simulations ---

def test_exercise_tests_and_the_simulation_appear_on_the_grades_screen(browser, bank):
    app, store, klass, lessons = world(bank)
    test = add_test(store, klass, lessons, 6)
    removed = add_test(store, klass, lessons, 12)
    finished(store, f"{test['id']}:1", "exercise_test", 55)
    finished(store, f"{test['id']}:1", "exercise_test", 80)
    finished(store, f"{test['id']}:2", "exercise_test", 70)
    finished(store, str(test["id"]), "simulation", 65)
    finished(store, f"{removed['id']}:1", "exercise_test", 90)
    store.remove_test(removed["id"])
    with running(app) as url:
        page = sign_in(browser, url, "#/grades")
        page.wait_for_selector("#exercise-grades")
        one = page.locator(f"#exercise-grades li[data-test='{test['id']}'][data-number='1']")
        assert one.locator(".gr-num").inner_text() == "80" and "2 ניסיונות" in one.inner_text() and "מבחן תרגול 1" in one.inner_text()
        assert page.locator(f"#exercise-grades li[data-test='{test['id']}'][data-number='2'] .gr-num").inner_text() == "70"
        assert page.locator(f"#simulation-grades li[data-test='{test['id']}'] .gr-num").inner_text() == "65"
        gone = page.locator(f"#exercise-grades li[data-test='{removed['id']}']")
        assert gone.locator(".gr-num").inner_text() == "90" and "הוסר" in gone.inner_text()               # a removed test keeps its grade and name
        assert page.locator("#no-grades").count() == 0 and page.locator("#quiz-grades").count() == 0
        no_sideways_scroll(page)
        page.click(f"#simulation-grades li[data-test='{test['id']}'] a")
        page.wait_for_selector("#test-card")


# --- 4.1 the teacher's tests tab ---

DESKTOP = {"width": 1280, "height": 800}


def teacher_page(browser, url, viewport=PHONE):
    page = offline_formulas(browser.new_page(viewport=viewport))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.fill("#email", TEACHER)
    page.click("#dev button")
    page.wait_for_selector("#teaching")
    page.click("#teacher-tabs [data-tab='tests']")
    page.wait_for_selector("#tests")
    page.errors = errors
    return page


def iso(days):
    return (clock.school_day() + timedelta(days=days)).isoformat()


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP])
def test_a_teacher_sets_a_test_with_the_defaults_moves_its_date_and_removes_it(browser, bank, viewport):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = teacher_page(browser, url, viewport)
        assert "עוד לא נקבע מבחן" in page.inner_text(".class-tests")
        page.click(".set-test summary")
        assert page.input_value("[name=questions]") == "12" and page.input_value("[name=minutes]") == "45"      # the defaults
        page.fill("[name=date]", iso(10))
        page.fill("[name=note]", "פרק 3")
        page.click(".set-test button[type=submit]")
        page.wait_for_selector(".test-row")
        row = page.locator(".test-row")
        assert "12 שאלות" in row.inner_text() and "45 דקות" in row.inner_text() and "בעוד 10 ימים" in row.inner_text() and "פרק 3" in row.inner_text()
        assert [t["questions"] for t in store.tests_of_classes([klass["id"]])] == [12]
        page.click("[data-edit]")                                                                                # move the date two days later
        page.fill(".edit-slot [name=date]", iso(12))
        page.click(".edit-slot button[type=submit]")
        page.wait_for_function("document.querySelector('.test-row h4').innerText.includes('בעוד 12 ימים')")
        page.click("[data-remove-test]")                                                                         # removing takes two steps
        page.click("[data-confirm-remove]")
        page.wait_for_selector(".test-row", state="detached")
        assert store.tests_of_classes([klass["id"]]) == [] and len(store.tests_of_classes([klass["id"]], include_removed=True)) == 1
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        assert page.errors == []


def test_the_tab_shows_who_has_not_taken_the_simulation_and_each_students_readiness(browser, bank):
    app, store, klass, lessons = world(bank)
    others = ["a@school.test", "b@school.test"]
    for email in others:
        store.add_member(klass["id"], email)
    test = add_test(store, klass, lessons, 5)
    now = clock.now()
    row = store.create_attempt(KID_ID, "simulation", str(test["id"]), now - timedelta(days=1), now - timedelta(days=1) + timedelta(minutes=45), [])
    store.save_attempt(row["id"], submitted_at=now - timedelta(days=1) + timedelta(minutes=5), grade=75)
    store.link_user(KID, KID_ID)
    with running(app) as url:
        page = teacher_page(browser, url)
        assert "1 מתוך 3 עשו סימולציה" in page.inner_text(".sim-count")
        missing = page.inner_text(".sim-missing")
        assert "a@school.test" in missing and "b@school.test" in missing and KID not in missing
        assert page.locator(".readiness-table tbody tr").count() == 3
        mine = page.locator(f".readiness-table tr:has-text('{KID}')")
        assert "28" in mine.inner_text() and "75" in mine.inner_text() and "0%" in mine.inner_text()        # M 0 and S 75: (30*75) / 80


def test_a_refused_test_shows_why_and_keeps_what_was_typed(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = teacher_page(browser, url)
        page.click(".set-test summary")
        page.fill("[name=date]", iso(10))
        page.fill("[name=note]", "לא לאבד")
        for box in page.locator(".set-test [name=lessons]").all():
            box.uncheck()                                                                                          # no lesson: the server refuses
        page.click(".set-test button[type=submit]")
        page.wait_for_selector(".set-test .form-error:not([hidden])")
        assert page.input_value(".set-test [name=note]") == "לא לאבד" and page.input_value(".set-test [name=date]") == iso(10)
        assert store.tests_of_classes([klass["id"]]) == []


# --- 5.1 the whole countdown ---

def answer_in_browser(page, bank, store, kind, scope, rights):
    """Answer the open attempt on screen right or wrong, one flag per question, moving with "next"; then submit."""
    page.wait_for_selector("#qz-q")
    refs = store.attempts_of(KID_ID, kind, scope)[-1]["questions"]
    for n, ok in enumerate(rights):
        key = page.get_attribute("#qz-q", "data-key")
        question = bank._questions[key.split(":")[0]][key]
        picks = [i for i, c in enumerate(question["choices"]) if bool(c.get("correct")) == ok]
        page.click(f"#qz-choices .qz-choice[data-i='{picks[0]}']")
        if n < len(rights) - 1:
            page.click(".qz-nav button >> nth=1")
            page.wait_for_function("(k) => document.querySelector('#qz-q').dataset.key !== k", arg=key)
    page.click("#qz-submit")
    page.wait_for_selector("#qz-grade")
    return refs


def test_the_whole_countdown_from_setting_a_test_to_the_review(browser, bank, monkeypatch):
    app, store, klass, lessons = world(bank)
    moment = {"now": clock.now()}
    monkeypatch.setattr(clock, "now", lambda: moment["now"])
    advance = lambda days: moment.update(now=moment["now"] + timedelta(days=days))
    skills = covered(bank, lessons)
    with running(app) as url:
        teacher = teacher_page(browser, url)                                                                   # the teacher sets a test 12 days ahead, 6 questions
        teacher.click(".set-test summary")
        teacher.fill("[name=date]", iso(12))
        teacher.fill("[name=questions]", "6")
        teacher.click(".set-test button[type=submit]")
        teacher.wait_for_selector(".test-row")
        test = store.tests_of_classes([klass["id"]])[0]
        student = sign_in(browser, url)
        to_home(student)
        task = lambda: student.get_attribute("#today-task", "href")
        reload_home = lambda: (student.goto(url + "#/subject/math"), student.reload(), student.wait_for_selector(".tabs"), student.wait_for_selector("#today-task"))

        assert task() == f"#/skill/{skills[0]}" and "לסיים את המסלול" in student.inner_text("#today-task")        # 12 days: finish the path
        assert "סימולציה" in student.inner_text(".rd-note")                                                      # the bar says it is capped until the simulation
        for i in skills:                                                                                        # the path is finished
            store.save_progress(KID_ID, i, started_at="then", mastered_at="then")
        reload_home()
        assert task() == f"#/exam/{test['id']}/1"                                                               # next: exercise test 1, early
        student.click("#today-task")
        answer_in_browser(student, bank, store, "exercise_test", f"{test['id']}:1", [True] * 6)
        assert student.inner_text("#qz-grade b") == "100"
        advance(3)                                                                                              # 9 days left
        reload_home()
        assert task() == f"#/exam/{test['id']}/2"                                                               # exercise test 2
        student.click("#today-task")
        answer_in_browser(student, bank, store, "exercise_test", f"{test['id']}:2", [True] * 6)
        advance(4)                                                                                              # 5 days left: the simulation opens
        reload_home()
        assert task() == f"#/sim/{test['id']}" and student.locator(f".required[data-required='{test['id']}']").count() == 1
        vals = lambda: {p: student.locator(f".rd-part[data-part={p}] .rd-val").inner_text() for p in "MES"}
        assert vals()["E"] == "100" and vals()["S"] == "—"
        student.click("#today-task")
        answer_in_browser(student, bank, store, "simulation", str(test["id"]), [True, True, True, True, False, False])
        assert student.inner_text("#qz-grade b") == "67"
        failed = [a.get_attribute("href") for a in student.locator("#qz-lost a").all()]
        assert failed
        advance(2)                                                                                              # 3 days left: review what failed
        reload_home()
        assert task() in failed and student.locator(".required").count() == 0                                   # a failed skill is today's review
        assert vals()["S"] == "67" and student.locator(".rd-note").count() == 0           # the cap is gone after the simulation
        teacher.reload()
        teacher.click("#teacher-tabs [data-tab='tests']")
        teacher.wait_for_selector(".test-row")
        assert "1 מתוך 1 עשו סימולציה" in teacher.inner_text(".sim-count")


# --- readiness-tooltip: the number explains itself ---

def test_the_readiness_tooltip_opens_on_tap_closes_three_ways_says_the_three_lines_and_fits_a_phone(browser, bank):
    app, store, klass, lessons = world(bank)
    add_test(store, klass, lessons, 7)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        page.wait_for_selector("#nearest-test [data-info]")
        button, tip = page.locator("#nearest-test [data-info]"), page.locator("#nearest-test .tip")
        assert button.get_attribute("aria-label") == "איך המדד מחושב" and tip.is_hidden()
        button.click()
        assert tip.is_visible() and button.get_attribute("aria-expanded") == "true"
        text = tip.inner_text()
        assert "שליטה (50%)" in text and "מבחני תרגול (20%)" in text and "סימולציה (30%)" in text and "לא נספר" in text and "לא עובר 80" in text
        box = tip.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= PHONE["width"]
        no_sideways_scroll(page)
        button.click()                                                                       # a second tap closes it (the mouse is moved away: hovering would show it)
        page.mouse.move(5, 5)
        assert tip.is_hidden() and button.get_attribute("aria-expanded") == "false"
        button.click()
        page.click("#nearest-test h2")                                                       # a tap elsewhere closes it
        assert tip.is_hidden() and button.get_attribute("aria-expanded") == "false"
        button.click()
        page.mouse.move(5, 5)
        page.keyboard.press("Escape")                                                        # so does Escape
        assert tip.is_hidden() and button.get_attribute("aria-expanded") == "false"
        assert not page.errors


def test_the_tooltip_is_on_the_tests_card_too_and_opens_on_hover_with_a_mouse(browser, bank):
    app, store, klass, lessons = world(bank)
    test = add_test(store, klass, lessons, 7)
    with running(app) as url:
        page = sign_in(browser, url, f"#/test/{test['id']}")
        to_home_card = page.wait_for_selector("[data-info]")
        page.hover("[data-info]")
        assert page.locator(".tip").first.is_visible() and "50%" in page.locator(".tip").first.inner_text()
        page.mouse.move(5, 5)
        assert page.locator(".tip").first.is_hidden()
