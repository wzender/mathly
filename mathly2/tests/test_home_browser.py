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
from mathly2.tests.serve import board_written

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
        assert page.get_attribute("#play", "href") == f"#/round/{lessons[0]}"
        no_sideways_scroll(page)





def test_home_shows_only_the_closest_test_and_the_other_tests_are_on_its_card(browser, bank):
    app, store, klass, lessons = world(bank)
    far = add_test(store, klass, lessons, 20)
    near = add_test(store, klass, lessons, 9)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        assert page.get_attribute("#nearest-test", "data-test") == str(near["id"]) and page.get_attribute("#home-sim", "href") == f"#/sim/{near['id']}"
        assert page.locator("#other-tests").count() == 0 and page.locator("#notifications").count() == 0                       # only what is critical
        page.click("#nearest-test .strip-main")
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
        assert "מבחן תרגול מאוזן" in page.inner_text(".mx-sheet") and page.locator(".qz-dot").count() == 6
        assert page.locator("#qz-timer").count() == 0                                                         # only the simulation is timed
        sheet = page.inner_text(".mx-sheet")
        assert not any(bank.skill(i)["name"] in sheet for i in skills)                                       # no skill names, no feedback
        page.click("#qz-submit")
        page.click("#qz-yes")
        page.wait_for_selector("#qz-grade")
        assert page.inner_text("#qz-grade b") == "0" and "תוצאת מבחן תרגול מאוזן" in page.inner_text(".mx-sheet")
        links = [a.get_attribute("href") for a in page.locator("#qz-lost a").all()]
        assert links and all(h.startswith("#/skill/") and h[8:] in skills for h in links)                    # weak skills link to their stars
        assert "המוכנות נשארה 0" in page.inner_text("#qz-ready") and page.locator("#qz-retake").count() == 0
        page.click(".qz-actions [data-close]")
        page.wait_for_function("(h) => location.hash === h", arg=f"#/test/{test['id']}")                    # closing leads back to the test's card
        page.wait_for_selector(".mx-sheet", state="detached")
        assert page.locator("#test-card").count() == 1



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




def test_after_the_simulation_the_wrong_questions_are_answered_again_in_a_round(browser, bank):
    app, store, klass, lessons = world(bank)
    started_skills(store, bank, lessons)
    test = add_test(store, klass, lessons, 4, questions=6, minutes=45)
    with running(app) as url:
        page = sign_in(browser, url, f"#/sim/{test['id']}")
        page.wait_for_selector("#qz-q")
        page.click("#qz-submit")                                                                        # nothing answered: six mistakes
        page.click("#qz-yes")
        page.wait_for_selector("#qz-retry")
        assert "(6)" in page.inner_text("#qz-retry")
        page.click("#qz-retry")
        page.wait_for_selector(".round-layer #ex-q")
        assert "חזרה על הטעויות" in page.inner_text(".round-layer .ex-chip") and "מתוך 6" in page.inner_text("#rd-count")
        context = page.inner_text("#rd-context")
        assert "מבחן סימולציה" in context and "שאלה 1 מתוך 6" in context and "לא עניתם" in context      # where the question came from
        for n in range(6):
            page.locator(".round-layer .ex-choice").first.click()
            page.wait_for_selector(".round-layer .ex-ok, .round-layer .ex-bad")
            page.click("#rd-next")
            if n < 5:
                page.wait_for_function(f"document.querySelector('#rd-count').textContent.includes('{n + 2} מתוך')")
        page.wait_for_selector("#rd-result[data-kind='retry']")
        assert "הציון במבחן לא משתנה" in page.inner_text("#rd-result") and page.locator(".rd-bigstars span").count() == 0
        assert store.attempts_of(KID_ID, "simulation")[0]["grade"] == 0
        page.click("#rd-result [data-close]")
        page.wait_for_selector(".round-layer", state="detached")                 # the card is already under the round: wait for the round to go
        assert page.locator("#test-card").count() == 1 and page.errors == []
        page.check("#practice input[value='focus']")                                                     # the hard skills now have their own test
        assert page.locator("#focus-skills .ex-chip").count() > 0
        page.click("#practice-start")
        page.wait_for_selector("#qz-q")
        assert "מבחן תרגול ממוקד" in page.inner_text(".mx-sheet h3") and 0 < page.locator(".qz-dot").count() <= 15
        focus = store.attempts_of(KID_ID, "exercise_test")[0]
        lost = {q["skill_id"] for q in store.attempts_of(KID_ID, "simulation")[0]["questions"]} | set(covered(bank, lessons)[:5])   # or still learning
        assert focus["scope"].endswith(":3") and {q["skill_id"] for q in focus["questions"]} <= lost and page.errors == []


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
        assert one.locator(".gr-num").inner_text() == "80" and "3 ניסיונות" in one.inner_text() and "מבחן תרגול מאוזן" in one.inner_text()   # 1 and the old 2: balanced
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
        assert "45 · " in mine.inner_text() and "1 · הטוב 75" in mine.inner_text()                           # one simulation of 75: 60% of the way


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
    """Answer the open attempt on screen right or wrong, one flag per question, moving with "next"; then submit. The board counts as written on."""
    board_written(page)
    page.wait_for_selector("#qz-q")
    refs = store.attempts_of(KID_ID, kind, scope)[-1]["questions"]
    for n, ok in enumerate(rights):
        key = page.get_attribute("#qz-q", "data-key")
        question = bank._questions[key.split(":")[0]][key]
        picks = [i for i, c in enumerate(question["choices"]) if bool(c.get("correct")) == ok]
        page.evaluate("window.MathlyBoard && (window.MathlyBoard.hasWork = () => true)")      # as if the way were on the board
        page.click(f"#qz-choices .qz-choice[data-i='{picks[0]}']")
        if n < len(rights) - 1:
            page.click(".qz-nav button >> nth=1")
            page.wait_for_function("(k) => document.querySelector('#qz-q').dataset.key !== k", arg=key)
    page.click("#qz-submit")
    page.wait_for_selector("#qz-grade")
    return refs



# --- readiness-tooltip: the number explains itself ---



# --- readiness: the home's block, the test's page, practice tests by mode and simulations on request ---

def test_home_finds_the_league_first_then_reveals_it_and_counts_up_after_practice(browser, bank):
    app, store, klass, lessons = world(bank)
    test = add_test(store, klass, lessons, 2)
    skills = covered(bank, lessons)
    day = clock.school_day()

    def answer(n, right=True):
        for skill in skills:
            for i in range(n):
                store.add_answer(KID_ID, skill, f"{skill}:{i}", right, True, None, day)

    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        strip = page.locator("#nearest-test")
        assert "מגלים את הליגה שלך" in strip.inner_text() and "מבחן בעוד 2 ימים" in strip.inner_text()   # no low number on day one
        assert page.inner_text("#home-forecast .fc-count") == "0/15" and "עוד 15 תשובות" in strip.inner_text()
        assert page.get_attribute("#nearest-test .strip-main", "href") == f"#/test/{test['id']}"
        assert page.inner_text("#home-practice").strip() == "📝 מבחן תרגול" and "+" not in page.inner_text("#home-sim")
        answer(1)                                                                                   # a few answers: the bar fills
        page.reload()
        page.wait_for_selector("#home-forecast.placing")
        page.wait_for_function(f"document.querySelector('#home-forecast .rd-num').textContent === '{len(skills)}'")   # counts up 0 -> 8
        answer(4)                                                                                   # enough: the league is revealed
        page.reload()
        page.wait_for_selector("#home-forecast[data-league]")
        assert "נחשפה הליגה שלך" in page.inner_text(".fc-cheer") and "ליגת" in page.inner_text("#home-forecast .rd-label")
        first = int(page.get_attribute("#home-forecast", "data-to"))
        answer(8)                                                                                   # more right answers: up, with +N
        page.reload()
        page.wait_for_selector("#home-forecast .rd-up")
        grade = int(page.get_attribute("#home-forecast", "data-to"))
        assert grade > first and page.inner_text("#home-forecast .rd-up") == f"+{grade - first}"
        page.click("#home-practice")                                                                # straight to choosing a practice test
        page.wait_for_selector("#practice .modes")
        no_sideways_scroll(page)


def test_a_written_simulation_is_checked_by_the_ai_then_raises_readiness_and_another_can_follow(browser, bank):
    from mathly2 import writtentest
    from mathly2.tests.test_boardreview_api import FakeReviewer

    class AllRight(FakeReviewer):
        def review_one(self, item, on_event=lambda step, **info: None):
            self.calls.append(item)
            return {"verdict": "correct", "feedback": "דרך מסודרת", "tip": "ככה ממשיכים"}

    app, store, klass, lessons = world(bank)
    app.state.reviewer = reviewer = AllRight()
    test = add_test(store, klass, lessons, 30, questions=4, minutes=20)                                 # a month ahead: no window
    with running(app) as url:
        page = sign_in(browser, url)
        board_written(page, pictures=True)
        to_home(page)
        page.click("#home-sim")
        page.wait_for_selector("#qz-timer")
        assert "מבחן סימולציה" in page.inner_text(".mx-sheet") and page.locator(".qz-dot").count() == 4
        assert page.locator(".qz-choice").count() == 0 and page.locator("#qz-written").count() == 1        # no choices: the board, like a real exam
        refs = {r["key"]: r for r in store.attempts_of(KID_ID, "simulation", str(test["id"]))[-1]["questions"]}
        boxes = 0
        for n in range(4):
            key = page.get_attribute("#qz-q", "data-key")
            final = writtentest.final_of(bank, refs[key])
            assert (page.locator("#qz-final").count() == 1) == (final is not None)                       # a box only for a plain number
            if final is not None:
                page.fill("#qz-final", str(final["value"]))
                boxes += 1
            if n < 3:
                page.click(".qz-nav button >> nth=1")
                page.wait_for_function("(k) => document.querySelector('#qz-q').dataset.key !== k", arg=key)
        page.click("#qz-submit")
        page.wait_for_selector("#qz-checking, #qz-grade")                                               # "בבדיקה" until the AI is done
        page.wait_for_selector("#qz-grade", timeout=20000)
        assert page.inner_text("#qz-grade b") == "100" and len(reviewer.calls) == 4
        assert sum(1 for c in reviewer.calls if c["typed"]) == boxes
        page.wait_for_selector("#qz-ready.up")
        assert page.inner_text(".qz-gain") == "+60" and "עלתה ל־60" in page.inner_text("#qz-ready") and "רמה חדשה: בדרך" in page.inner_text("#qz-ready")
        page.click("#qz-more-sim")                                                                   # another one, on request
        page.wait_for_selector("#qz-timer")
        assert len(store.attempts_of(KID_ID, "simulation")) == 2 and page.errors == []


def test_the_tests_page_has_three_practice_modes_and_the_trail_of_gains(browser, bank):
    app, store, klass, lessons = world(bank)
    skills = covered(bank, lessons)
    test = add_test(store, klass, lessons, 10, questions=4)
    finished(store, f"{test['id']}:1", "exercise_test", 50)
    with running(app) as url:
        page = card_page(browser, url, test["id"])
        page.wait_for_function("document.querySelector('#test-card .readiness:not(.forecast) .rd-num').textContent === '15'")
        assert [m.get_attribute("data-mode") for m in page.locator("#practice .mode").all()] == ["balanced", "focus", "manual"]
        assert page.locator("#practice input[value='focus']").is_disabled()                          # nothing hard yet (no questions in that one)
        assert "+15" in page.inner_text("#trail") and "מבחן תרגול מאוזן" in page.inner_text("#trail")
        page.check("#practice input[value='manual']")
        assert page.locator("#manual-skills").is_visible() and page.locator("#manual-skills input").count() == len(skills)
        page.click("#practice-start")
        assert "בחרו לפחות" in page.inner_text("#practice-error")
        page.check(f"#manual-skills input[value='{skills[0]}']")
        page.click("#practice-start")
        page.wait_for_selector("#qz-q")
        row = store.attempts_of(KID_ID, "exercise_test", f"{test['id']}:4")[0]
        assert "מבחן תרגול בבחירה" in page.inner_text(".mx-sheet h3") and {q["skill_id"] for q in row["questions"]} == {skills[0]}
        page.click(".mx-x")
        page.wait_for_selector("#practice")
        page.click("#rd-how summary")
        assert "סימולציה סוגר 60%" in page.inner_text("#rd-how") and "העמקה נספרת" in page.inner_text("#rd-deepening") and page.errors == []
        no_sideways_scroll(page)


def test_without_the_ai_a_written_simulation_waits_for_the_teacher(browser, bank):
    app, store, klass, lessons = world(bank)
    test = add_test(store, klass, lessons, 30, questions=4, minutes=20)
    with running(app) as url:
        page = sign_in(browser, url, f"#/sim/{test['id']}")
        board_written(page, pictures=True)
        page.wait_for_selector("#qz-written")
        page.click(".qz-nav button >> nth=1")                                                         # every board here counts as written on
        page.click("#qz-submit")
        page.wait_for_selector("#qz-checking")
        assert "ממתין לבדיקת המורה" in page.inner_text("#qz-checking") and page.locator("#qz-grade").count() == 0
        assert store.attempts_of(KID_ID, "simulation")[0]["grade"] is None and page.errors == []


def test_a_league_is_held_through_a_small_dip_and_going_up_is_cheered(browser, bank):
    app, store, klass, lessons = world(bank)
    with running(app) as url:
        page = sign_in(browser, url)
        to_home(page)
        show = """async ([grade, seen]) => {
            const m = await import('/static/home.js');
            if (seen === null) localStorage.removeItem('mathly2.forecast.99'); else localStorage.setItem('mathly2.forecast.99', JSON.stringify(seen));
            const leagues = [{at: 0, name: 'ירח', icon: '🌙'}, {at: 55, name: 'כוכב לכת', icon: '🪐'}, {at: 70, name: 'כוכב', icon: '⭐'}, {at: 85, name: 'גלקסיה', icon: '🌌'}];
            const league = leagues.map(l => l.at).filter(at => grade >= at).length - 1;
            const box = document.createElement('div');
            box.innerHTML = m.forecastMeter({grade, low: grade - 5, high: grade + 5, answers: 40, placement: null, league, leagues, keep: 3}, 99, {});
            const el = box.firstElementChild;
            return {league: Number(el.dataset.league), cheer: box.querySelector('.fc-cheer')?.textContent || ''};
        }"""
        held = page.evaluate(show, [68, {"grade": 72, "league": 2, "done": 40}])
        assert held == {"league": 2, "cheer": ""}                                                   # 68 is within 3 of ⭐ at 70: kept
        dropped = page.evaluate(show, [64, {"grade": 72, "league": 2, "done": 40}])
        assert dropped["league"] == 1 and dropped["cheer"] == ""                                    # a real drop: shown quietly
        up = page.evaluate(show, [71, {"grade": 66, "league": 1, "done": 40}])
        assert up["league"] == 2 and "עליתם לליגת ⭐ כוכב" in up["cheer"]
        revealed = page.evaluate(show, [60, {"grade": 40, "league": -1, "done": 14}])
        assert revealed["league"] == 1 and "נחשפה הליגה שלך" in revealed["cheer"]
        assert page.errors == []
