"""The teacher's progress tab (add-class-progress-views 2.1), in a real browser."""
import pytest

playwright = pytest.importorskip("playwright.sync_api")

from mathly2 import clock
from mathly2.tests.serve import offline_formulas, running
from mathly2.tests.test_written_browser import DESKTOP, KID, KID2, PHONE, TEACHER, bank, browser, day, uid, world  # noqa: F401

STAMP = "2026-10-05T10:00:00+00:00"


def open_progress(browser, url, viewport=PHONE, via="tab"):
    page = offline_formulas(browser.new_page(viewport=viewport))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url)
    page.fill("#email", TEACHER)
    page.click("#dev button")
    page.wait_for_selector("#teaching")
    if via == "tab":
        page.click("#teacher-tabs [data-tab=progress]")
    else:
        page.click(".class-card [data-progress]")
    page.wait_for_selector("#progress table, #progress .muted")
    page.errors = errors
    return page


def no_sideways(page):
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@pytest.mark.parametrize("viewport", [PHONE, DESKTOP], ids=["390px", "1280px"])
def test_progress_is_per_lesson_each_cell_says_its_state_and_the_table_scrolls_inside_its_frame(browser, bank, viewport):
    app, store, klass, lessons = world(bank)
    skills = [s["id"] for s in bank.skills if s["unit"] == "t"]
    store.save_progress(uid(KID), skills[0], started_at=STAMP, mastered_at=STAMP)
    for s in skills:
        store.save_progress(uid(KID2), s, started_at=STAMP, mastered_at=STAMP)
    store.add_member(klass["id"], "new@school.test")
    with running(app) as url:
        page = open_progress(browser, url, viewport)
        assert page.locator("#progress tbody tr").count() == 3 and page.locator("th.skill-col, .hm td.c").count() == 0         # no skill column or cell
        cell = lambda who: page.locator(f"tr[data-student='{who}'] td[data-lesson=t]")
        assert cell(KID).get_attribute("data-state") == "learning" and cell(KID).get_attribute("aria-label") == "בלמידה"
        assert cell(KID2).get_attribute("data-state") == "completed" and cell(KID2).get_attribute("aria-label") == "הושלם" and cell(KID2).inner_text().split() == ["100%", "—"]
        assert cell("new@school.test").get_attribute("data-state") == "not_started" and cell("new@school.test").get_attribute("aria-label") == "לא התחילו"
        assert cell("new@school.test").inner_text().split() == ["0%", "—"]                                       # a bar with its percent and a dash: nothing else
        assert page.locator("td.cov .pbar").count() == page.locator("td.cov").count() and "בוחן" not in page.inner_text("tbody")
        assert page.locator("td.cov:not([data-state])").count() == 0 
        assert page.evaluate("(() => { const w = document.querySelector('.tablewrap'); return w.scrollWidth > w.clientWidth; })()") or viewport["width"] > 800
        no_sideways(page)
        assert not page.errors


def test_the_card_shortcut_the_picker_the_views_and_the_periods(browser, bank):
    app, store, klass, lessons = world(bank)
    other = store.create_class("setup", "B", lessons=lessons[:1], teacher_email=TEACHER)
    store.create_test(klass["id"], day(10), ["t"], TEACHER, created_at=clock.now())
    with running(app) as url:
        page = open_progress(browser, url, via="card")
        assert page.locator("#class-pick option").count() == 2 and "לפי שיעור" in page.inner_text("#view-tabs")
        page.click("#period-tabs [data-period='2']")
        page.wait_for_function("document.querySelector('#period-tabs [data-period=\"2\"]').getAttribute('aria-pressed') === 'true'")
        assert page.locator("th.lesson-col").count() > 0 and page.locator("td.cov .pbar").count() > 0
        page.click("#view-tabs [data-view=readiness]")
        assert page.locator("#period-tabs").count() == 0 and "מוכנות" in page.inner_text("#progress table")
        page.select_option("#class-pick", str(other["id"]))
        page.wait_for_selector("#no-test")                                                                  # class B has no coming test
        no_sideways(page)


def test_the_table_marks_a_completed_and_a_behind_lesson_in_words(browser, bank):
    app, store, klass, lessons = world(bank)
    skills = [s["id"] for s in bank.skills if s["unit"] == "t"]
    for s in skills:
        store.save_progress(uid(KID), s, started_at=STAMP, mastered_at=STAMP)
    store.set_lesson_dates({"t": day(-3)})
    with running(app) as url:
        page = open_progress(browser, url)
        assert page.get_attribute(f"tr[data-student='{KID}'] td[data-lesson=t]", "aria-label") == "הושלם" and page.locator(f"tr[data-student='{KID}'] [data-behind]").count() == 0
        assert page.get_attribute(f"tr[data-student='{KID2}'] td[data-lesson=t]", "aria-label") == "לא התחילו, בפיגור"
        assert page.locator(f"tr[data-student='{KID2}'] td[data-lesson=t] [data-behind]").inner_text() == "⚠"           # the visual mark
        assert page.inner_text("#teacher-tabs [data-tab=progress] .tab-count") == "2"                       # the tab's number: the students
        no_sideways(page)
