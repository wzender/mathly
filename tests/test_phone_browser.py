"""Optional browser regression checks: pip install playwright && playwright install chromium."""
import socket
import threading
import time

import pytest
import uvicorn

from app.main import create_app

playwright = pytest.importorskip("playwright.sync_api")


@pytest.fixture
def phone_server(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "browser-test")
    app = create_app()

    class Solver:
        def solve(self, image, media_type):
            assert image and media_type == "image/jpeg"
            return {"readable": True, "problem": "Triangle", "steps": [{"hint": "Hint", "work": "Work"}],
                    "answer": "10 cm", "skill": "", "note": ""}

    app.state.photo, app.state.photo_key = Solver(), "browser-test"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(.01)
            yield f"http://127.0.0.1:{sock.getsockname()[1]}"
        finally:
            server.should_exit = True
            thread.join(timeout=5)


@pytest.mark.parametrize("manager", [True, False])
def test_class_management_geometry_and_permissions(phone_server, manager):
    import json

    row = {"id": 7, "name": "כיתת תרגול", "lessons": ["t"],
           "emails": ["student@example.com", "teacher@example.com"], "teachers": ["teacher@example.com"],
           "exam_title": "לוח מבחנים – כיתה ט׳11, תשפ״ז",
           "exam_note": "ייתכנו שינויים.",
           "exams": [{"date": "2026-11-16", "subject": "מתמטיקה"}]}
    writes = []
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            page.add_init_script('''window.supabase={createClient:()=>({auth:{
                getSession:async()=>({data:{session:{access_token:"test",user:{id:"test"}}}}),
                onAuthStateChange:()=>{},signOut:async()=>{}
            }})};''')

            def index(route):
                response = route.fetch()
                route.fulfill(response=response, body=response.text().replace(
                    'supabaseUrl:""', 'supabaseUrl:"https://auth.invalid"'))

            page.route(phone_server + "/", index)
            page.route("**/api/me", lambda route: route.fulfill(json={
                "email": "student@example.com", "user_id": "test", "answer_scans": False,
                "permissions": ["management.access", "classes.manage"] if manager else ["path.use"],
                "classes": [row]}))
            page.route("**/api/classes", lambda route: route.fulfill(json={"classes": [row]}))

            def save(route):
                body = json.loads(route.request.post_data)
                writes.append(body)
                if len(writes) == 1:
                    route.fulfill(status=503, json={"detail": "temporary failure"})
                else:
                    row.update(body)
                    route.fulfill(json={"ok": True})

            page.route("**/api/classes/7", save)
            page.goto(phone_server)
            playwright.expect(page.get_by_role("heading", name="המקצועות שלי")).to_be_visible()
            page.locator('[data-subject="מתמטיקה"]').click()
            button = page.locator('[data-act="manage"]')
            if not manager:
                playwright.expect(page.locator('.mx-top')).to_be_visible()
                playwright.expect(button).to_have_count(0)
                return
            playwright.expect(page.locator(".mx-exam-countdown")).to_be_visible()
            playwright.expect(page.locator(".mx-exam-countdown time")).to_contain_text("16 בנובמבר 2026")
            button.click()
            playwright.expect(page.locator(".mx-exam-board")).to_contain_text("מתמטיקה")
            page.get_by_role("button", name="+ כיתה חדשה").click()
            subject = page.locator('input[name="subject"][value="מתמטיקה"]')
            units = page.locator('input[name="unit"][data-subject="מתמטיקה"]')
            playwright.expect(subject).not_to_be_checked()
            playwright.expect(page.locator('[data-subject-units="מתמטיקה"]')).to_be_hidden()
            subject.check()
            playwright.expect(page.locator('[data-subject-units="מתמטיקה"]')).to_be_visible()
            assert units.count() > 1 and all(units.nth(i).is_checked() for i in range(units.count()))
            units.first.uncheck()
            assert subject.evaluate("input => input.checked && input.indeterminate")
            subject.uncheck()
            assert not any(units.nth(i).is_checked() for i in range(units.count()))
            page.get_by_role("button", name="ביטול").click()
            page.get_by_role("button", name="עריכה").click()
            playwright.expect(page.locator('input[name="subject"][value="מתמטיקה"]')).to_be_checked()
            geometry = page.locator('input[name="unit"][value="a"]')
            geometry.check()
            page.get_by_role("button", name="שמירת השינויים").click()
            playwright.expect(page.get_by_role("status")).to_contain_text("לא הצלחנו לשמור")
            playwright.expect(geometry).to_be_checked()
            page.get_by_role("button", name="שמירת השינויים").click()
            playwright.expect(page.get_by_role("status")).to_contain_text("השינויים נשמרו")
            assert writes[-1] == {"name": row["name"], "emails": row["emails"],
                                  "teachers": row["teachers"], "lessons": ["t", "a"]}
            page.locator('.mx-x').click()
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator('[data-id="a_30_side"]')).to_be_visible()
            page.reload()
            page.locator('[data-subject="מתמטיקה"]').click()
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator('[data-id="a_30_side"]')).to_be_visible()
        finally:
            browser.close()


def test_class_teacher_report(phone_server):
    """A student chosen as the class's teacher opens the class report: progress, difficulties and both kinds of grades."""
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    slips = [{"at": (now - timedelta(days=d)).isoformat(), "id": "t_ext", "q": 0, "m": "ext_partial"} for d in (1, 3)]
    row = {"id": 4, "name": "ט׳2", "lessons": ["t"], "teacher": True, "exams": []}
    report = {"class": {"id": 4, "name": "ט׳2", "lessons": ["t"]}, "students": [
        {"email": "dana@example.com", "signed_in": True, "saved_at": None, "progress": {
            "done": {"t_ext": "2026-11-01"}, "gold": {}, "days": {}, "missed": {}, "slips": slips, "updated": 1,
            "quizzes": [{"at": "2026-11-02T10:00:00Z", "n": 12, "right": 9, "ms": 600000, "units": ["t"]}],
            # the device claims 85; the server's own record of the sitting says 62
            "uq": {"t": {"history": [{"at": "2026-11-03T10:00:00Z", "score": 85, "sid": "s1"}], "going": False}}},
         "quiz_sittings": [{"id": "s1", "unit_id": "t", "submitted_at": "2026-11-04T10:00:00Z", "grade": 62, "open": 0}]},
        {"email": "omer@example.com", "signed_in": False, "saved_at": None, "progress": None, "quiz_sittings": []},
        {"email": "noa@example.com", "signed_in": True, "saved_at": None, "progress": {   # handed in, a check still waits
            "done": {}, "gold": {}, "days": {}, "missed": {}, "slips": [], "updated": 1, "quizzes": [],
            "uq": {"t": {"history": [{"at": "2026-11-04T09:00:00Z", "sid": "s2"}], "going": False}}},
         "quiz_sittings": [{"id": "s2", "unit_id": "t", "submitted_at": "2026-11-04T09:00:00Z", "grade": None, "open": 1}]},
        {"email": "ben@example.com", "signed_in": True, "saved_at": None, "progress": {   # from before the server kept sittings
            "done": {}, "gold": {}, "days": {}, "missed": {}, "slips": [], "updated": 1, "quizzes": [],
            "uq": {"t": {"history": [{"at": "2026-10-20T09:00:00Z", "score": 100}], "going": False}}},
         "quiz_sittings": []}]}
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            page.add_init_script('''window.supabase={createClient:()=>({auth:{
                getSession:async()=>({data:{session:{access_token:"test",user:{id:"test"}}}}),
                onAuthStateChange:()=>{},signOut:async()=>{}
            }})};''')

            def index(route):
                response = route.fetch()
                route.fulfill(response=response, body=response.text().replace(
                    'supabaseUrl:""', 'supabaseUrl:"https://auth.invalid"'))

            page.route(phone_server + "/", index)
            page.route("**/api/me", lambda route: route.fulfill(json={
                "email": "teacher@example.com", "user_id": "test", "answer_scans": False,
                "permissions": ["path.use"], "classes": [row]}))
            page.route("**/api/math/progress", lambda route: route.fulfill(json={"progress": {}}))
            page.route("**/api/classes/4/report", lambda route: route.fulfill(json=report))
            page.goto(phone_server)
            page.locator('[data-act="class-report"]').click()
            sheet = page.locator(".mx-report-sheet")
            playwright.expect(sheet.locator("#mxTitle")).to_have_text("הכיתה שלי: ט׳2")
            playwright.expect(sheet.locator(".mx-report-common")).to_contain_text("1 תלמידים: dana")
            dana, omer = sheet.locator(".mx-report-student").nth(0), sheet.locator(".mx-report-student").nth(1)
            playwright.expect(dana.locator("summary")).to_contain_text("בוחן 62")
            playwright.expect(dana.locator("summary")).to_contain_text("תרגול 9/12")
            playwright.expect(omer).to_contain_text("עוד לא נכנס לחשבון")
            dana.locator("summary").click()
            quiz = dana.locator("section", has_text="בוחן מסכם").locator(".mx-report-table")
            playwright.expect(quiz).to_contain_text("62/100")
            playwright.expect(quiz).not_to_contain_text("85")   # the device's number is never shown
            playwright.expect(dana.locator(".mx-report-table").nth(1)).to_contain_text("75")
            # the practice data says it comes from the device; the quiz grades do not
            playwright.expect(dana.locator("section h5", has_text="התקדמות ביחידות")).to_contain_text("נתוני תרגול מהמכשיר")
            playwright.expect(dana.locator("section h5", has_text="מבחני תרגול")).to_contain_text("נתוני תרגול מהמכשיר")
            playwright.expect(dana.locator("section h5", has_text="בחני היחידה")).not_to_contain_text("מהמכשיר")
            noa, ben = sheet.locator(".mx-report-student").nth(2), sheet.locator(".mx-report-student").nth(3)
            noa.locator("summary").click(); ben.locator("summary").click()
            # columns: the official (final) grade, then the latest practice sitting
            playwright.expect(noa.locator(".mx-report-grade")).to_have_text(["–", "ממתין לבדיקה"])
            playwright.expect(ben.locator(".mx-report-grade")).to_have_text(["–", "לא מאומת"])   # not "100"
            playwright.expect(ben.locator(".mx-report-student, summary").first).not_to_contain_text("בוחן 100")
            page.locator(".mx-report-sheet .mx-x").click()
            playwright.expect(sheet).to_be_hidden()
        finally:
            browser.close()


def open_report(p, server, students, now=None, lessons=("t",), me=None, routes=None, assignments=None):
    """The class teacher's report for class 4 (lessons: unit t) with these students; returns (browser, page, sheet)."""
    from datetime import datetime
    row = {"id": 4, "name": "ט׳2", "lessons": list(lessons), "teacher": True, "exams": []}
    report = {"class": {"id": 4, "name": "ט׳2", "lessons": list(lessons)}, "students": students, "assignments": assignments}
    browser = p.chromium.launch()
    page = browser.new_page()
    page.clock.set_fixed_time(now or datetime(2026, 11, 4, 12))   # a Wednesday: this week began on Sunday 1 November
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    page.add_init_script('''window.supabase={createClient:()=>({auth:{
        getSession:async()=>({data:{session:{access_token:"test",user:{id:"test"}}}}),
        onAuthStateChange:()=>{},signOut:async()=>{}
    }})};''')

    def index(route):
        response = route.fetch()
        route.fulfill(response=response, body=response.text().replace('supabaseUrl:""', 'supabaseUrl:"https://auth.invalid"'))

    page.route(server + "/", index)
    page.route("**/api/me", lambda route: route.fulfill(json={
        "email": "teacher@example.com", "user_id": "test", "answer_scans": False,
        "permissions": ["path.use"], "classes": [row], **(me or {})}))
    page.route("**/api/math/progress", lambda route: route.fulfill(json={"progress": {}}))
    page.route("**/api/classes/4/report", lambda route: route.fulfill(json=report))
    if routes:
        routes(page)
    page.goto(server)
    page.locator('[data-act="class-report"]').click()
    return browser, page, page.locator(".mx-report-sheet")


def pupil(email, days=None, slips=(), signed_in=True, progress=True, **extra):
    base = {"done": {}, "gold": {}, "days": days or {}, "missed": {}, "slips": list(slips), "updated": 1, "quizzes": [], "uq": {}}
    return {"email": email, "signed_in": signed_in, "saved_at": None, "quiz_sittings": [],
            "progress": {**base, **extra} if progress else None}


def test_a_class_teacher_sees_only_their_classes_until_they_view_as_a_student(phone_server):
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [pupil("dana@example.com")])
        try:
            sheet.locator('[data-act="preview-on"]').click()
            playwright.expect(page.locator(".mx-preview")).to_contain_text("מצב תצוגה כתלמיד")
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator(".mx-pghead")).to_contain_text("המסלול שלי")   # the trail, as a student has it
            playwright.expect(page.locator('[data-act="class-report"]')).to_have_count(0)
            page.locator('[data-act="preview-off"]').click()
            playwright.expect(page.locator(".mx-preview")).to_have_count(0)
            playwright.expect(page.locator(".mx-pghead")).to_have_count(0)
            playwright.expect(page.locator('[data-act="class-report"]')).to_have_count(1)
        finally:
            browser.close()


def test_a_students_card_lists_the_skills_where_they_opened_the_worked_example(phone_server):
    students = [pupil("dana@example.com", {"2026-11-03": 5}, examples={
                    "t_ext": {"n": 3, "last": "2026-11-02T10:00:00Z"},       # this week
                    "t_simplify": {"n": 1, "last": "2026-10-25T10:00:00Z"},   # within two weeks
                    "t_area": {"n": 4, "last": "2026-10-01T10:00:00Z"},       # too long ago
                    "g_pyth": {"n": 2, "last": "2026-11-03T10:00:00Z"}}),     # not a skill of this class
                pupil("omer@example.com", {"2026-11-03": 5})]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students)
        try:
            dana = sheet.locator("#rs-0")
            dana.locator("summary").click()
            helped = dana.locator("section", has_text="דוגמאות פתורות")
            playwright.expect(helped.locator("li")).to_have_count(2)
            playwright.expect(helped.locator("li").nth(0)).to_contain_text("3 פעמים")        # the newest first
            playwright.expect(helped.locator("li").nth(1)).to_contain_text("פעם אחת")
            playwright.expect(helped.locator("h5")).to_contain_text("נתוני תרגול מהמכשיר")
            omer = sheet.locator("#rs-1")
            omer.locator("summary").click()
            assert omer.locator("section", has_text="דוגמאות פתורות").count() == 0
        finally:
            browser.close()


def test_the_report_opens_with_the_students_who_need_attention(phone_server):
    stuck = [{"at": f"2026-11-0{d}T09:00:00Z", "id": "t_ext", "q": 0, "m": "ext_partial"} for d in (1, 2, 3)]
    students = [pupil("ben@example.com", {"2026-11-03": 5, "2026-10-27": 7}),
                pupil("dana@example.com", {"2026-10-27": 6}),
                pupil("eli@example.com", {"2026-11-03": 5}, slips=stuck),
                pupil("noa@example.com", progress=False),
                pupil("omer@example.com", signed_in=False, progress=False)]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students)
        try:
            attn = sheet.locator(".mx-report-attn")
            playwright.expect(attn.locator("h4")).to_have_text("דורשים תשומת לב")
            items = attn.locator("li")
            playwright.expect(items).to_have_count(3)   # ben is fine; omer has not signed in yet
            playwright.expect(items.nth(0)).to_contain_text("dana")
            playwright.expect(items.nth(0)).to_contain_text("לא תרגל 8 ימים")
            playwright.expect(items.nth(1)).to_contain_text("eli")
            playwright.expect(items.nth(1)).to_contain_text("תקוע במיומנות")
            playwright.expect(items.nth(2)).to_contain_text("noa")
            playwright.expect(items.nth(2)).to_contain_text("עוד לא התחיל לתרגל")
            assert "ben" not in attn.inner_text()
            # a name in the list opens that student's card
            eli = sheet.locator("#rs-2")   # the card's id is the student's place in the class list
            assert eli.get_attribute("open") is None
            items.nth(1).locator("button").click()
            assert eli.get_attribute("open") is not None
            # this week and last week on a card
            ben = sheet.locator("#rs-0")
            ben.locator("summary").click()
            playwright.expect(ben.locator(".mx-report-week")).to_have_text("5 תשובות נכונות השבוע · 7 בשבוע שעבר")
        finally:
            browser.close()


def test_the_report_says_when_nobody_needs_attention(phone_server):
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [pupil("ben@example.com", {"2026-11-03": 5})])
        try:
            playwright.expect(sheet.locator(".mx-report-attn")).to_contain_text("אף תלמיד לא דורש תשומת לב כרגע")
            playwright.expect(sheet.locator(".mx-report-attn li")).to_have_count(0)
        finally:
            browser.close()


def test_the_class_map_colours_each_students_units_and_opens_a_unit_by_skill(phone_server):
    from app.math_skills import algebra9
    skills = [x["id"] for x in algebra9()["skills"] if x["unit"] == "t"]
    first, second = skills[0], skills[1]
    fresh = "2026-10-30T10:00:00Z"
    students = [
        pupil("ana@example.com", {"2026-11-03": 5}, done={first: fresh}, gold={first: fresh}, seen={first: fresh}, tries={first: 6, second: 3}, missed={second: ["m"]}),
        pupil("cy@example.com", {"2026-10-20": 5}, tries={second: 2}, missed={second: ["m"]}),
        {**pupil("eve@example.com", progress=False), "name": "נועה ל."}]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students, lessons=[u["id"] for u in algebra9()["units"][:6]])
        try:
            row = lambda who: sheet.locator("tbody tr", has=page.locator(f"th:text-is('{who}')"))
            # a choice saved by the topic version of the map (other column names) does not keep November closed
            page.evaluate("localStorage.setItem('mathly.report.mapOpen', '|אלגברה וחזקות'); localStorage.setItem('mathly.report.unit', 't')")   # and a unit saved by the old table: the map still opens on its months
            sheet.locator("[data-report-tab=map]").click()
            sheet.locator("[data-report-sort]").select_option("name")
            playwright.expect(sheet.locator("tbody th")).to_have_text(["נועה ל.", "ana", "cy"])
            # first level: a column per month of the syllabus, with the students' progress over all its units; the current month (November) is open
            months = sheet.locator("thead [data-heat-group]")
            playwright.expect(months).to_have_count(3)            # September, October, November: the first six units
            playwright.expect(months.first).to_contain_text("ספטמבר")
            playwright.expect(sheet.locator(".mx-heat-unit")).to_have_count(2)   # November's units (q, q2) are open
            playwright.expect(sheet.locator("[data-heat-group=נובמבר]")).to_have_attribute("aria-expanded", "true")
            assert "stuck" in row("ana").locator(".mx-heat-cell").first.get_attribute("class")
            months.first.click()                                   # opens into its two units (t and k)
            playwright.expect(sheet.locator(".mx-heat-unit")).to_have_count(4)
            playwright.expect(months.first).to_have_attribute("aria-expanded", "true")
            ana, cy, eve = (row(w).locator(".mx-heat-cell").first for w in ("ana", "cy", "נועה ל."))
            playwright.expect(ana).to_have_text(f"{round(100 / len(skills))}%")     # one skill finished
            assert "stuck" in ana.get_attribute("class")                            # and the second is still open
            assert "h0" in cy.get_attribute("class") and "stuck" in cy.get_attribute("class")   # practised, finished nothing
            playwright.expect(eve).to_have_attribute("aria-label", "עוד לא התחיל לתרגל")
            # a unit's name opens that unit by skill, and the choice shows in the unit list
            sheet.locator("[data-heat-all=close]").click()
            playwright.expect(sheet.locator(".mx-heat-unit")).to_have_count(0)
            sheet.locator("[data-heat-all=open]").click()
            playwright.expect(sheet.locator(".mx-heat-unit")).to_have_count(6)
            sheet.locator("[data-heat-unit=t]").click()
            playwright.expect(sheet.locator("[data-report-unit]")).to_have_value("t")
            playwright.expect(sheet.locator("thead th")).to_have_count(1 + len(skills))
            playwright.expect(row("ana").locator(".mx-cell").first).to_have_attribute("aria-label", "כוכב זהב")
            sheet.locator("[data-report-unit]").select_option("overview")
            playwright.expect(sheet.locator(".mx-heat")).to_be_visible()
            # many units are wider than a phone: the map scrolls inside its own box, never the page or the sheet
            page.set_viewport_size({"width": 375, "height": 700})
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert sheet.evaluate("el => el.scrollWidth <= el.clientWidth")
        finally:
            browser.close()


def test_a_students_card_says_where_they_stand_and_lists_only_the_units_they_started(phone_server):
    from app.math_skills import algebra9
    skills = [x["id"] for x in algebra9()["skills"] if x["unit"] == "t"]
    students = [pupil("ana@example.com", {"2026-11-03": 5}, missed={skills[1]: ["m"]}),
                pupil("bo@example.com", {"2026-11-03": 5}, done={skills[0]: "2026-11-03T10:00:00Z"}),
                pupil("cy@example.com", {"2026-10-01": 5}, done={skills[0]: "2026-10-01T10:00:00Z"})]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students, lessons=[u["id"] for u in algebra9()["units"][:3]])
        try:
            card = lambda who: sheet.locator(".mx-report-student", has=page.locator(f"b:text-is('{who}')"))
            playwright.expect(card("ana").locator("summary .mx-report-chip").first).to_have_text("תקוע")
            playwright.expect(card("bo").locator("summary .mx-report-chip").first).to_have_text("פעיל")
            playwright.expect(card("cy").locator("summary .mx-report-chip").first).to_have_text("לא פעיל")   # a month ago
            playwright.expect(card("bo").locator(".mx-spark")).to_have_attribute("aria-label", "5 תשובות נכונות ב־14 הימים האחרונים")
            card("bo").locator("summary").click()
            playwright.expect(card("bo").locator(".mx-quiz-units-score > div")).to_have_count(1)   # the unit they started
            playwright.expect(card("bo")).to_contain_text("עוד 2 יחידות בלי פעילות")
        finally:
            browser.close()


def test_the_reports_order_and_view_are_kept_and_names_come_from_the_class(phone_server):
    students = [pupil("cy@example.com", {"2026-10-31": 5}),   # all practised within the week: nobody has a signal
                {**pupil("ana@example.com", {"2026-11-03": 5}), "name": "אנה כהן"},
                pupil("bo@example.com", {"2026-10-29": 5}),
                pupil("dov@example.com", {"2026-11-02": 5})]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students)
        try:
            order = lambda: sheet.locator(".mx-report-student > summary > b").all_inner_texts()
            sort = sheet.locator("[data-report-sort]")
            assert order() == ["cy", "אנה כהן", "bo", "dov"]                    # nobody has a signal: the class's order
            sort.select_option("name")
            assert order() == ["אנה כהן", "bo", "cy", "dov"]
            sort.select_option("activity")
            assert order() == ["bo", "cy", "dov", "אנה כהן"] and order() != ["cy", "אנה כהן", "bo", "dov"]   # longest ago first
            sheet.locator("#rs-1 summary").click()
            playwright.expect(sheet.locator("#rs-1")).to_contain_text("ana@example.com")   # the full email stays in the card
            sort.select_option("progress")
            sheet.locator("[data-report-tab=subs]").click()
            # the choices stay when the report is opened again
            sheet.locator(".mx-x").click()
            page.locator('[data-act="class-report"]').click()
            playwright.expect(sheet.locator("[data-report-sort]")).to_have_value("progress")
            playwright.expect(sheet.locator("[data-report-tab=subs]")).to_have_attribute("aria-pressed", "true")
        finally:
            browser.close()


def sitting_of(*attempts, unit="t", grade=None):
    return {"id": "sit-1", "unit_id": unit, "submitted_at": "2026-11-04T09:00:00Z", "grade": grade, "open": 0,
            "attempts": list(attempts), "questions": [{"points": 25, "earned": 25, "state": "checked"} for _ in attempts]}


def answer_of(attempt_id, review=None, request=None):
    return {"attempt": {"id": attempt_id, "question_id": "quiz:t:1", "snapshot": {"name": "בוחן מסכם: שאלה 2", "question": "פתרו: $x + 1 = 3$"}},
            "attachment": {"id": "att"}, "student": {"email": "dana@example.com"},
            "grading": {"state": "completed", "result": {"verdict": "partial", "score": 40, "feedback": "חסר פירוט",
                                                         "transcription": "x = 2", "solution": "$x = 2$"}},
            "review": review, "request": request, "effective_score": 40}


PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360000002000001e221bc330000000049454e44ae426082")


def test_the_teacher_opens_a_quiz_answer_and_saves_a_score_and_a_comment(phone_server):
    import json
    students = [{**pupil("dana@example.com"), "quiz_sittings": [sitting_of("a1", "a2", "a3", "a4", grade=100)]}]
    puts, state = [], {"review": None}

    def routes(page):
        def answer(route):
            route.fulfill(json=answer_of("a2", state["review"], {"id": "r1", "state": "open", "message": "כתבתי x=2", "created_at": "2026-11-04T10:00:00Z"}))

        def save(route):
            puts.append(json.loads(route.request.post_data))
            state["review"] = {"id": "v1", "score": puts[-1].get("score"), "comment": puts[-1].get("comment", ""),
                               "created_at": "2026-11-04T11:00:00Z", "reviewer_email": "t@x"}
            route.fulfill(json={"review": state["review"], "request": {"id": "r1", "state": "closed", "message": "כתבתי x=2"}})

        page.route("**/api/teacher/answers/a2", lambda route: save(route) if route.request.method == "GET" and False else answer(route))
        page.route("**/api/teacher/answers/a2/review", save)
        page.route("**/api/teacher/answers/a2/image", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students, routes=routes)
        try:
            sheet.locator("#rs-0 summary").click()
            sheet.locator("[data-answers]").click()                                   # the answers of the latest sitting
            sheet = page.locator(".mx-tr-sheet")
            playwright.expect(sheet.locator("#mxTitle")).to_contain_text("תשובות בבוחן")
            playwright.expect(sheet.locator("[data-review-answer]")).to_have_count(4)
            sheet.locator("[data-review-answer]").nth(1).click()
            playwright.expect(sheet.locator(".mx-tr-request")).to_contain_text("כתבתי x=2")   # the student's request
            playwright.expect(sheet.locator(".mx-tr-ai")).to_contain_text("40/100")
            playwright.expect(sheet.locator(".mx-tr-ai")).to_contain_text("חסר פירוט")
            playwright.expect(sheet.locator(".mx-tr-img")).to_be_visible()
            form = sheet.locator("[data-review-form]")
            form.locator("[name=score]").fill("150")                                  # out of range: the page's own limit
            assert form.locator("[name=score]").evaluate("el => el.validity.rangeOverflow")
            form.locator("[name=score]").fill("90")
            form.locator("[name=comment]").fill("הדרך נכונה, טעות חישוב")
            form.locator("[type=submit]").click()
            playwright.expect(form.locator("[role=status]")).to_contain_text("נשמר")
            assert puts == [{"score": 90, "comment": "הדרך נכונה, טעות חישוב"}]
            playwright.expect(sheet.locator("section", has_text="הבדיקה שלכם")).to_contain_text("90/100")
            playwright.expect(sheet.locator(".mx-tr-request")).to_have_count(0)   # answered: the request is closed
            sheet.locator("[data-review-back]").click()                               # back to the sitting's answers
            playwright.expect(sheet.locator("#mxTitle")).to_contain_text("תשובות בבוחן")
            sheet.locator("[data-review-back]").click()                               # and to the report
            playwright.expect(page.locator(".mx-report-sheet #mxTitle")).to_contain_text("הכיתה שלי")
        finally:
            browser.close()


def test_a_comment_alone_is_saved_without_a_score_and_a_teacher_without_access_is_told(phone_server):
    import json
    students = [{**pupil("dana@example.com"), "quiz_sittings": [sitting_of("a1", "a2", "a3", "a4", grade=100)]}]
    puts = []

    def routes(page):
        page.route("**/api/teacher/answers/a1", lambda route: route.fulfill(json=answer_of("a1")))
        page.route("**/api/teacher/answers/a1/image", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))
        page.route("**/api/teacher/answers/a1/review", lambda route: (puts.append(json.loads(route.request.post_data)),
                   route.fulfill(json={"review": {"score": None, "comment": "יפה", "created_at": "2026-11-04T11:00:00Z"}, "request": None}))[1])
        page.route("**/api/teacher/answers/a3", lambda route: route.fulfill(status=403, json={"detail": "forbidden"}))
        page.route("**/api/teacher/answers/a3/image", lambda route: route.fulfill(status=403, json={"detail": "forbidden"}))

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students, routes=routes)
        try:
            sheet.locator("#rs-0 summary").click()
            sheet.locator("[data-answers]").click()
            sheet = page.locator(".mx-tr-sheet")
            sheet.locator("[data-review-answer]").nth(2).click()
            playwright.expect(sheet.locator(".mx-manage-state")).to_have_text("אין לכם הרשאה לתשובה הזו.")
            sheet.locator("[data-review-back]").click()
            sheet.locator("[data-review-answer]").nth(0).click()
            form = sheet.locator("[data-review-form]")
            form.locator("[name=comment]").fill("יפה")
            form.locator("[type=submit]").click()
            playwright.expect(form.locator("[role=status]")).to_contain_text("נשמר")
            assert puts == [{"comment": "יפה"}]                                       # no score key: the AI's score stays
        finally:
            browser.close()


def test_a_handled_request_in_the_queue_opens_the_answer(phone_server):
    rows = [{"id": "q1", "state": "done", "kind": "grading", "email": "dana@example.com", "attempt_id": "a2", "label": "בוחן: שאלה 2",
             "question": "פתרו", "created_at": "2026-11-04T08:00:00Z", "result": {"verdict": "partial", "score": 40}},
            {"id": "q2", "state": "done", "kind": "photo", "email": "dana@example.com", "attempt_id": None, "label": "תרגיל",
             "created_at": "2026-11-04T08:00:00Z", "result": {"readable": True, "answer": "3"}}]

    def routes(page):
        page.route("**/api/ai-queue", lambda route: route.fulfill(json={"requests": rows, "all": False}))
        page.route("**/api/teacher/answers/a2", lambda route: route.fulfill(json=answer_of("a2")))
        page.route("**/api/teacher/answers/a2/image", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [pupil("dana@example.com")], me={"ai_review": True}, routes=routes)
        try:
            sheet.locator(".mx-x").click()
            page.locator('[data-act="ai-queue"]').first.click()
            queue = page.locator(".mx-aq-sheet")
            playwright.expect(queue.locator("[data-review-answer]")).to_have_count(1)   # only an answer, not a photographed problem
            queue.locator("[data-review-answer]").click()
            playwright.expect(page.locator(".mx-tr-sheet .mx-tr-ai")).to_contain_text("40/100")
            page.locator("[data-review-back]").click()
            playwright.expect(page.locator(".mx-aq-sheet")).to_be_visible()
        finally:
            browser.close()


def test_requests_to_look_again_have_their_own_tab_and_count_in_the_queue_button(phone_server):
    asking = [{"id": "r1", "attempt_id": "a2", "student": "dana@example.com", "message": "כתבתי x=2", "question": "בוחן: שאלה 2",
               "created_at": "2026-11-04T10:00:00Z"}]
    waiting = [{"id": "q1", "state": "pending", "kind": "grading", "email": "omer@example.com", "attempt_id": "a9", "label": "תרגיל",
                "question": "פתרו", "created_at": "2026-11-04T08:00:00Z"}]
    students = [{**pupil("dana@example.com"), "review_requests": [
        {"attempt_id": "a2", "message": "כתבתי x=2", "question": "בוחן: שאלה 2", "created_at": "2026-11-04T10:00:00Z"}]}]

    def routes(page):
        page.route("**/api/ai-queue", lambda route: route.fulfill(json={"requests": waiting, "all": False}))
        page.route("**/api/ai-queue/q1/image", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))
        page.route("**/api/teacher/review-requests", lambda route: route.fulfill(json={"requests": asking}))
        page.route("**/api/teacher/answers/a2", lambda route: route.fulfill(json=answer_of(
            "a2", None, {"id": "r1", "state": "open", "message": "כתבתי x=2", "created_at": "2026-11-04T10:00:00Z"})))
        page.route("**/api/teacher/answers/a2/image", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students, me={"ai_review": True}, routes=routes)
        try:
            # the report names the student who asked, and opens the answer; back leads to the report
            playwright.expect(sheet.locator("#rs-0 summary")).to_contain_text("ביקש בדיקה חוזרת")
            sheet.locator("#rs-0 summary").click()
            sheet.locator("#rs-0 [data-review-answer]").click()
            playwright.expect(page.locator(".mx-tr-request")).to_contain_text("כתבתי x=2")
            page.locator("[data-review-back]").click()
            playwright.expect(page.locator(".mx-report-sheet #mxTitle")).to_contain_text("הכיתה שלי")
            page.locator(".mx-report-sheet .mx-x").click()
            # one waiting request and one student asking to look again: the button says 2
            button = page.locator('[data-act="ai-queue"]').first
            playwright.expect(button).to_contain_text("2")
            button.click()
            queue = page.locator(".mx-aq-sheet")
            playwright.expect(queue.locator("[data-aq-tab=queue]")).to_have_attribute("aria-pressed", "true")
            playwright.expect(queue.locator(".mx-aq-card")).to_have_count(1)           # the waiting request
            queue.locator("[data-aq-tab=requests]").click()
            playwright.expect(queue.locator("[data-aq-tab=requests]")).to_contain_text("1")
            card = queue.locator(".mx-aq-card")
            playwright.expect(card).to_have_count(1)
            playwright.expect(card).to_contain_text("dana")
            playwright.expect(card).to_contain_text("כתבתי x=2")
            card.locator("[data-review-answer]").click()
            playwright.expect(page.locator(".mx-tr-sheet .mx-tr-ai")).to_contain_text("40/100")
            page.locator("[data-review-back]").click()
            playwright.expect(page.locator(".mx-aq-sheet [data-aq-tab=requests]")).to_have_attribute("aria-pressed", "true")   # the tab is kept
        finally:
            browser.close()


def open_student_app(p, server, assignments, sittings=(), progress=None, now=None):
    """A student of class 4 (units t and k) on the path, with these assignments from the server; returns (browser, page)."""
    from datetime import datetime
    row = {"id": 4, "name": "ט׳2", "lessons": ["t", "k"], "teacher": False, "exams": []}
    browser = p.chromium.launch()
    page = browser.new_page()
    page.clock.set_fixed_time(now or datetime(2026, 11, 4, 12))
    page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
    page.add_init_script('''window.supabase={createClient:()=>({auth:{
        getSession:async()=>({data:{session:{access_token:"test",user:{id:"test"}}}}),
        onAuthStateChange:()=>{},signOut:async()=>{}
    }})};''')

    def index(route):
        response = route.fetch()
        route.fulfill(response=response, body=response.text().replace('supabaseUrl:""', 'supabaseUrl:"https://auth.invalid"'))

    page.route(server + "/", index)
    page.route("**/api/me", lambda route: route.fulfill(json={
        "email": "student@example.com", "user_id": "test", "answer_scans": False, "permissions": ["path.use"], "classes": [row]}))
    page.route("**/api/math/progress", lambda route: route.fulfill(json={"progress": progress or {}}))
    page.route("**/api/math/assignments", lambda route: route.fulfill(json={
        "assignments": assignments, "sittings": list(sittings), "today": "2026-11-04"}))
    page.goto(server)
    page.locator('.mx-nav [data-view="home"]').click()   # the assignments are on home
    return browser, page


def given(title, due, items, id=None, created="2026-11-01T10:00:00Z"):
    return {"id": id or title, "class_id": 4, "class_name": "ט׳2", "title": title, "note": "", "due_on": due,
            "items": items, "created_at": created, "updated_at": created}


SKILL, QUIZ, EXAM = {"kind": "skill", "id": "t_ext"}, {"kind": "unit_quiz", "unit": "k"}, {"kind": "exam", "units": ["k", "t"]}


def test_the_home_screen_lists_the_open_assignments_late_ones_and_the_recently_done(phone_server):
    assignments = [
        given("חזרה לפני המבחן", "2026-11-12", [SKILL, QUIZ, EXAM], "open"),
        given("משימה שאיחרה", "2026-11-02", [{"kind": "skill", "id": "t_simplify"}], "late"),
        given("משימה שהסתיימה", "2026-11-01", [SKILL], "done"),
        given("משימה ישנה שהסתיימה", "2026-10-01", [SKILL], "old")]
    progress = {"done": {"t_ext": "2026-09-01T10:00:00Z"}}
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, assignments, progress=progress)
        try:
            cards = page.locator(".mx-asgs .mx-asg")
            playwright.expect(cards).to_have_count(2)                                   # the finished ones are not cards
            playwright.expect(cards.nth(0)).to_contain_text("משימה שאיחרה")              # the earliest due date first
            playwright.expect(cards.nth(0)).to_contain_text("באיחור")
            assert "late" in cards.nth(0).get_attribute("class")
            open_ = cards.nth(1)
            playwright.expect(open_).to_contain_text("חזרה לפני המבחן")
            playwright.expect(open_).to_contain_text("1 מתוך 3 הושלמו")
            items = open_.locator(".mx-asg-items li")
            assert [items.nth(i).get_attribute("class") for i in range(3)] == ["done", "", ""]
            playwright.expect(items.nth(1)).to_contain_text("בוחן חיזוק")
            playwright.expect(items.nth(2)).to_contain_text("מבחן תרגול")
            playwright.expect(open_.locator("[data-asg-go]")).to_contain_text("להמשיך: בוחן חיזוק")   # the next one to do
            done = page.locator(".mx-asg-done")
            playwright.expect(done.locator("summary")).to_have_text("הושלמו (1)")
            done.locator("summary").click()
            playwright.expect(done).to_contain_text("משימה שהסתיימה")
            assert "משימה ישנה שהסתיימה" not in page.locator(".mx-asgs").inner_text()
        finally:
            browser.close()


def test_continue_opens_the_first_item_that_is_not_done(phone_server):
    first = [given("ראשון", "2026-11-12", [SKILL, QUIZ, EXAM], "a")]
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, first)                         # nothing done: the skill
        try:
            playwright.expect(page.locator("[data-asg-go]")).to_contain_text("להתחיל")
            page.locator("[data-asg-go]").click()
            playwright.expect(page.locator(".mx-sheet h3").first).to_contain_text("חוק הפילוג המורחב")
        finally:
            browser.close()
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, first, progress={"done": {"t_ext": "2026-09-01T10:00:00Z"}})
        try:                                                                              # the skill done: the unit quiz
            page.locator("[data-asg-go]").click()
            playwright.expect(page.locator(".mx-uq-sheet")).to_be_visible()
        finally:
            browser.close()
    sitting = [{"unit_id": "k", "submitted_at": "2026-11-03T09:00:00Z"}]
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, first, sitting, {"done": {"t_ext": "2026-09-01T10:00:00Z"}})
        try:                                                                              # then the practice exam, with its units chosen
            playwright.expect(page.locator("[data-asg-go]")).to_contain_text("להמשיך: מבחן תרגול")
            page.locator("[data-asg-go]").click()
            units = page.locator(".mx-quiz-sheet [data-quiz-unit]")
            playwright.expect(page.locator(".mx-quiz-sheet")).to_contain_text("המורה ביקש מבחן תרגול")
            assert units.count() >= 2 and all(units.nth(i).get_attribute("aria-pressed") == "true" for i in range(units.count()))
        finally:
            browser.close()


def test_a_finished_assignment_leaves_the_card_and_the_skills_of_open_ones_wear_a_marker(phone_server):
    assignments = [given("חזרה", "2026-11-12", [SKILL, {"kind": "skill", "id": "t_simplify"}], "a"),
                   given("עוד אחת", "2026-11-12", [SKILL], "b")]
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, assignments)
        try:
            page.locator('.mx-nav [data-view="path"]').click()   # the markers are on the trail
            star = page.locator('.mx-star[data-id="t_ext"]')
            playwright.expect(star.locator(".mx-asg-pin")).to_have_count(1)
            label = star.get_attribute("aria-label")
            assert "משימה מהמורה: חזרה, עוד אחת" in label                                  # both assignments name it
            playwright.expect(page.locator('.mx-star[data-id="t_simplify"] .mx-asg-pin')).to_have_count(1)
            assert "משימה מהמורה: חזרה" in page.locator('.mx-star[data-id="t_simplify"]').get_attribute("aria-label")
            assert page.locator('.mx-star[data-id="t_ext_eq"] .mx-asg-pin').count() == 0   # not assigned: no marker
            assert "משימה" not in page.locator('.mx-star[data-id="t_ext_eq"]').get_attribute("aria-label")
        finally:
            browser.close()
    done = {"done": {"t_ext": "2026-09-01T10:00:00Z", "t_simplify": "2026-09-02T10:00:00Z"}}
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, assignments, progress=done)
        try:
            playwright.expect(page.locator(".mx-asgs")).to_contain_text("הושלמו (2)")
            assert page.locator(".mx-asg-pin").count() == 0 and page.locator(".mx-asg").count() == 0
        finally:
            browser.close()


def test_each_assignment_says_how_much_time_is_left_to_hand_in(phone_server):
    """Noon UTC on Wednesday 4 November is 14:00 in Jerusalem: the due day itself has 10 hours left."""
    assignments = [given(title, due, [SKILL], title) for title, due in (
        ("אתמול", "2026-11-03"), ("לפני שלושה ימים", "2026-11-01"), ("היום", "2026-11-04"), ("מחר", "2026-11-05"),
        ("בעוד שלושה ימים", "2026-11-07"))]
    with playwright.sync_playwright() as p:
        from datetime import datetime, timezone
        browser, page = open_student_app(p, phone_server, assignments, now=datetime(2026, 11, 4, 12, tzinfo=timezone.utc))
        try:
            due = lambda title: page.locator(".mx-asg", has_text=title).locator(".mx-asg-due")
            playwright.expect(due("לפני שלושה ימים")).to_contain_text("באיחור של 3 ימים")
            playwright.expect(due("אתמול")).to_contain_text("באיחור של יום")
            playwright.expect(due("היום")).to_contain_text("היום, נשארו כ־10 שעות")
            playwright.expect(due("מחר")).to_contain_text("מחר, נשאר יום אחד")
            playwright.expect(due("בעוד שלושה ימים")).to_contain_text("נשארו 3 ימים")
            assert "soon" in due("היום").get_attribute("class") and "soon" in due("מחר").get_attribute("class")
            assert "soon" not in due("בעוד שלושה ימים").get_attribute("class")
        finally:
            browser.close()


def test_the_home_screen_is_quiet_without_assignments(phone_server):
    with playwright.sync_playwright() as p:
        browser, page = open_student_app(p, phone_server, [])
        try:
            playwright.expect(page.locator(".mx-continue")).to_be_visible()
            assert page.locator(".mx-asgs").count() == 0
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator(".mx-star").first).to_be_visible()
            assert page.locator(".mx-asg-pin").count() == 0
        finally:
            browser.close()


def taught(title, due, items, id=None, created="2026-11-01T10:00:00Z"):
    return {"id": id or title, "class_id": 4, "title": title, "note": "", "due_on": due, "items": items,
            "created_by_email": "teacher@example.com", "created_at": created, "updated_at": created}


ASG_STUDENTS = [
    # all three items done: the skill long ago, the unit quiz and the practice exam after the assignment was made
    {**pupil("dana@example.com", {"2026-11-03": 5}, done={"t_ext": "2026-09-01T10:00:00Z"},
             quizzes=[{"at": "2026-11-03T09:00:00Z", "n": 12, "right": 9, "units": ["k", "t"]}]),
     "quiz_sittings": [{"id": "s1", "unit_id": "k", "submitted_at": "2026-11-03T09:00:00Z", "grade": 90, "open": 0}]},
    {**pupil("noa@example.com", {"2026-11-03": 5}, done={"t_ext": "2026-09-01T10:00:00Z"}), "quiz_sittings": []},
    {**pupil("omer@example.com", {"2026-11-03": 5}), "quiz_sittings": []}]


def test_the_assignments_tab_shows_how_many_finished_and_who_did_what(phone_server):
    assignments = [taught("חזרה לפני המבחן", "2026-11-12", [SKILL, QUIZ, EXAM], "a"),
                   taught("משימה ישנה", "2026-11-02", [SKILL], "b")]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, lessons=["t", "k"], assignments=assignments)
        try:
            sheet.locator("[data-report-tab=tasks]").click()
            cards = sheet.locator(".mx-asg-t")
            playwright.expect(cards).to_have_count(2)
            playwright.expect(cards.nth(0)).to_contain_text("חזרה לפני המבחן")             # the latest due date first
            playwright.expect(cards.nth(0)).to_contain_text("1 מתוך 3 תלמידים סיימו")
            playwright.expect(cards.nth(1)).to_contain_text("המועד עבר")
            playwright.expect(cards.nth(1)).to_contain_text("2 מתוך 3 תלמידים סיימו")      # the skill alone: dana and noa
            first = cards.nth(0)
            first.locator("summary").click()
            row = lambda who: first.locator("tbody tr", has=page.locator(f"th:text-is('{who}')")).locator("td.mx-asg-cell")
            playwright.expect(row("dana")).to_have_text(["✓", "✓", "✓"])
            playwright.expect(row("noa")).to_have_text(["✓", "–", "–"])
            playwright.expect(row("omer")).to_have_text(["–", "–", "–"])
            state = lambda who: first.locator("tbody tr", has=page.locator(f"th:text-is('{who}')")).locator("td.mx-task-state")
            playwright.expect(state("dana")).to_have_text("הוגש")          # the same state the student sees
            playwright.expect(state("noa")).to_have_text("בתהליך")
            playwright.expect(state("omer")).to_have_text("עוד לא התחיל")
        finally:
            browser.close()


def test_a_student_who_is_late_with_an_assignment_needs_attention(phone_server):
    assignments = [taught("משימה ישנה", "2026-11-02", [SKILL], "b")]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, assignments=assignments)
        try:
            attn = sheet.locator(".mx-report-attn li")
            playwright.expect(attn).to_have_count(1)                                       # omer: dana and noa finished it
            playwright.expect(attn).to_contain_text("omer")
            playwright.expect(attn).to_contain_text("משימה באיחור: משימה ישנה")
        finally:
            browser.close()


def test_the_assignments_tab_says_when_assignments_cannot_be_read(phone_server):
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, assignments=None)
        try:
            sheet.locator("[data-report-tab=tasks]").click()
            playwright.expect(sheet).to_contain_text("המשימות אינן זמינות כרגע")
            assert sheet.locator("[data-asg-new]").count() == 0
        finally:
            browser.close()


MANAGES = {"permissions": ["path.use", "management.access"]}   # skills, quizzes and exams in an assignment: developers only


def asg_routes(sent, saved):
    """POST/PUT/DELETE of class 4's assignments, kept in `sent`; `saved(body, id)` makes the answer."""
    import json

    def handle(route):
        request = route.request
        body = json.loads(request.post_data) if request.post_data else None
        sent.append((request.method, request.url.rsplit("/assignments", 1)[1], body))
        if request.method == "DELETE":
            return route.fulfill(json={"ok": True})
        route.fulfill(status=201 if request.method == "POST" else 200, json=saved(body, request.url.rsplit("/", 1)[1]))

    return lambda page: page.route("**/api/classes/4/assignments**", handle)


def test_the_teacher_makes_an_assignment_with_the_form(phone_server):
    sent = []
    made = lambda body, _id: {**taught(body["title"], body["due_on"], body["items"], "new"), "note": body["note"]}
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, lessons=["t", "k"], assignments=[],
                                           routes=asg_routes(sent, made), me=MANAGES)
        try:
            sheet.locator("[data-report-tab=tasks]").click()
            playwright.expect(sheet).to_contain_text("עוד לא נתתם משימות")
            sheet.locator("[data-asg-new]").click()
            form = sheet.locator("[data-asg-form]")
            status = form.locator("[role=status]")
            form.locator("button[type=submit]").click()
            playwright.expect(status).to_have_text("כתבו כותרת למשימה.")
            form.locator("[name=title]").fill("חזרה לפני המבחן")
            form.locator("button[type=submit]").click()
            playwright.expect(status).to_contain_text("בחרו לפחות פריט אחד")
            form.locator("[name=note]").fill("בהצלחה")
            form.locator("[name=due_on]").fill("2026-11-14")
            form.locator("details", has_text="טכניקה אלגברית 1").first.locator("summary").click()
            form.locator("[name=skill][value=t_ext]").check()
            form.locator("[name=skill][value=t_simplify]").check()
            form.locator("[name=quiz][value=k]").check()
            form.locator("[name=exam][value=t]").check()
            form.locator("[name=exam][value=k]").check()
            form.locator("button[type=submit]").click()
            playwright.expect(sheet.locator(".mx-asg-t")).to_have_count(1)
            playwright.expect(sheet.locator(".mx-asg-t")).to_contain_text("חזרה לפני המבחן")
            playwright.expect(sheet).to_contain_text("המשימה נשמרה")
            assert sent == [("POST", "", {"title": "חזרה לפני המבחן", "note": "בהצלחה", "due_on": "2026-11-14", "items": [
                {"kind": "skill", "id": "t_ext"}, {"kind": "skill", "id": "t_simplify"}, {"kind": "unit_quiz", "unit": "k"},
                {"kind": "exam", "units": ["t", "k"]}]})]
            assert sheet.locator("[data-asg-form]").count() == 0
        finally:
            browser.close()


def test_the_teacher_edits_an_assignment_and_a_refusal_is_explained(phone_server):
    sent = []
    changed = lambda body, id_: {**taught(body["title"], body["due_on"], body["items"], id_), "note": body["note"]}
    assignments = [taught("חזרה", "2026-11-12", [SKILL, QUIZ, EXAM], "a")]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, lessons=["t", "k"], assignments=assignments,
                                           routes=asg_routes(sent, changed), me=MANAGES)
        try:
            sheet.locator("[data-report-tab=tasks]").click()
            sheet.locator("[data-asg-edit=a]").click()
            form = sheet.locator("[data-asg-form]")
            playwright.expect(form.locator("[name=title]")).to_have_value("חזרה")
            playwright.expect(form.locator("[name=due_on]")).to_have_value("2026-11-12")
            playwright.expect(form.locator("[name=skill][value=t_ext]")).to_be_checked()
            playwright.expect(form.locator("[name=quiz][value=k]")).to_be_checked()
            assert form.locator("[name=exam]:checked").count() == 2
            form.locator("[name=title]").fill("חזרה מורחבת")
            form.locator("[name=due_on]").fill("2026-11-15")
            form.locator("button[type=submit]").click()
            playwright.expect(sheet.locator(".mx-asg-t")).to_contain_text("חזרה מורחבת")
            assert sent[0][0] == "PUT" and sent[0][1] == "/a" and sent[0][2]["due_on"] == "2026-11-15"
            assert sent[0][2]["items"] == [SKILL, QUIZ, {"kind": "exam", "units": ["t", "k"]}]   # the form's items, in unit order
            sheet.locator("[data-asg-edit=a]").click()
            sheet.locator("[data-asg-cancel]").click()                                    # cancelling changes nothing
            assert len(sent) == 1 and sheet.locator("[data-asg-form]").count() == 0
        finally:
            browser.close()
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, assignments=[], routes=lambda pg: pg.route(
            "**/api/classes/4/assignments**", lambda route: route.fulfill(status=403, json={"detail": "x"})), me=MANAGES)
        try:
            sheet.locator("[data-report-tab=tasks]").click()
            sheet.locator("[data-asg-new]").click()
            form = sheet.locator("[data-asg-form]")
            form.locator("[name=title]").fill("x")
            form.locator("details").first.locator("summary").click()
            form.locator("[name=skill]").first.check()
            form.locator("button[type=submit]").click()
            playwright.expect(form.locator("[role=status]")).to_have_text("רק מורה הכיתה יכול לתת לה משימות.")
            playwright.expect(form.locator("button[type=submit]")).to_be_enabled()
        finally:
            browser.close()


def test_deleting_an_assignment_asks_first_and_says_how_many_already_did_part_of_it(phone_server):
    sent, messages = [], []
    assignments = [taught("חזרה", "2026-11-12", [SKILL, QUIZ], "a")]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, ASG_STUDENTS, lessons=["t", "k"], assignments=assignments,
                                           routes=asg_routes(sent, lambda body, id_: body))
        try:
            def answer(accept):
                def on_dialog(dialog):
                    messages.append(dialog.message)
                    dialog.accept() if accept else dialog.dismiss()
                page.once("dialog", on_dialog)

            sheet.locator("[data-report-tab=tasks]").click()
            answer(False)
            sheet.locator("[data-asg-del=a]").click()
            page.wait_for_timeout(200)
            assert sent == [] and sheet.locator(".mx-asg-t").count() == 1                 # dismissed: nothing is deleted
            answer(True)
            sheet.locator("[data-asg-del=a]").click()
            playwright.expect(sheet.locator(".mx-asg-t")).to_have_count(0)
            assert sent == [("DELETE", "/a", None)]
            assert 'למחוק את המשימה "חזרה"' in messages[0] and "2 תלמידים כבר השלימו" in messages[0]   # dana and noa did the skill
            assert messages[1] == messages[0]
        finally:
            browser.close()


def test_class_editor_takes_the_teacher_as_free_text(phone_server):
    import json

    row = {"id": 7, "name": "ט׳3", "lessons": ["t"], "emails": ["a@example.com", "b@example.com"],
           "teachers": ["b@example.com"], "exams": []}
    writes = []
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            page.add_init_script('''window.supabase={createClient:()=>({auth:{
                getSession:async()=>({data:{session:{access_token:"test",user:{id:"test"}}}}),
                onAuthStateChange:()=>{},signOut:async()=>{}
            }})};''')

            def index(route):
                response = route.fetch()
                route.fulfill(response=response, body=response.text().replace(
                    'supabaseUrl:""', 'supabaseUrl:"https://auth.invalid"'))

            def save(route):
                writes.append(json.loads(route.request.post_data))
                route.fulfill(json={"ok": True})

            page.route(phone_server + "/", index)
            page.route("**/api/me", lambda route: route.fulfill(json={
                "email": "boss@example.com", "user_id": "test", "answer_scans": False,
                "permissions": ["management.access", "classes.manage"], "classes": []}))
            page.route("**/api/math/progress", lambda route: route.fulfill(json={"progress": {}}))
            page.route("**/api/classes", lambda route: route.fulfill(json={"classes": [row]}))
            page.route("**/api/classes/7", save)
            page.goto(phone_server)
            page.locator('[data-act="manage"]').click()
            playwright.expect(page.locator(".mx-class-card")).to_contain_text("b@example.com")
            page.get_by_role("button", name="עריכה").click()
            teacher = page.locator('input[name="teacher"]')
            playwright.expect(teacher).to_have_value("b@example.com")
            teacher.fill("t@example.com")
            page.locator('textarea[name="emails"]').fill("a@example.com\nt@example.com\nc@example.com")
            page.get_by_role("button", name="שמירת השינויים").click()
            playwright.expect(page.locator(".mx-class-form [role=status]")).to_contain_text("מורה לא יכול להיות גם תלמיד")
            page.locator('textarea[name="emails"]').fill("a@example.com\nb@example.com\nc@example.com")
            page.get_by_role("button", name="שמירת השינויים").click()
            playwright.expect(page.locator(".mx-manage-state")).not_to_have_text("שומרים…")
            assert writes[-1]["teachers"] == ["t@example.com"]
            assert writes[-1]["emails"] == ["a@example.com", "b@example.com", "c@example.com"]
        finally:
            browser.close()


# ---- focus areas: where each student, and the class, most need work (Sky.focus), and giving practice from there
def lost_on(skill, earned, at="2026-11-03T09:00:00Z"):
    return {"id": "sit-" + skill, "unit_id": "t", "submitted_at": at, "grade": 50, "open": 0, "mode": "final",
            "attempts": [], "questions": [{"points": 25, "earned": earned, "state": "checked", "skills": [skill]}]}


def test_a_students_card_says_what_to_work_on_with_its_evidence(phone_server):
    slips = [{"at": "2026-11-02T09:00:00Z", "id": "t_ext_eq", "q": 0, "m": "sign_mid"}] * 4
    dana = {**pupil("dana@example.com", slips=slips, tries={"t_ext_eq": 3}), "quiz_sittings": [lost_on("t_ext_eq", 13)]}
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [dana, pupil("noa@example.com")])
        try:
            card = sheet.locator(".mx-report-student").filter(has_text="dana")
            card.locator("summary").first.click()
            focus = card.locator(".mx-focus")
            first = focus.locator(".mx-focus-list li").first
            playwright.expect(first).to_contain_text("איבד 12 נק׳ בבחנים")              # the server's evidence, no device tag
            playwright.expect(first).to_contain_text("4 טעויות ב־14 ימים · לא הושלם")
            playwright.expect(first.locator(".mx-device")).to_have_text("· מהמכשיר")   # the device's evidence is labelled
            first.locator("[data-focus-give]").click()
            form = sheet.locator("[data-focus-form]")
            playwright.expect(form.locator('[name=skill][value="t_ext_eq"]')).to_be_checked()
            playwright.expect(form.locator('[name=student][value="dana@example.com"]')).to_be_checked()
            playwright.expect(form.locator('[name=student][value="noa@example.com"]')).not_to_be_checked()
            sheet.locator("[data-report-tab=list]").click()
            noa = sheet.locator(".mx-report-student").filter(has_text="noa")
            noa.locator("summary").first.click()
            playwright.expect(noa.locator(".mx-focus")).to_contain_text("אין כרגע מיומנות שצריך לחזק")
        finally:
            browser.close()


def test_the_class_view_lists_the_shared_weak_skills_and_gives_practice_to_those_students(phone_server):
    weak = lambda email: {**pupil(email, tries={"t_area": 2}), "quiz_sittings": [lost_on("t_area", 5)]}
    students = [weak("dana@example.com"), weak("noa@example.com"), pupil("omer@example.com")]
    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, students)
        try:
            sheet.locator("[data-report-tab=focus]").click()
            item = sheet.locator(".mx-focus-list li").first
            playwright.expect(item).to_contain_text("2 תלמידים")
            item.locator("details summary").click()
            playwright.expect(item.locator("details")).to_contain_text("dana · noa")
            item.locator("[data-focus-give]").click()
            form = sheet.locator("[data-focus-form]")
            playwright.expect(form.locator('[name=skill][value="t_area"]')).to_be_checked()
            playwright.expect(form.locator("[name=student]:checked")).to_have_count(2)
            playwright.expect(form.locator('[name=student][value="omer@example.com"]')).not_to_be_checked()
        finally:
            browser.close()


# ---- the teacher's inbox: one list of what waits, opened one after another; and releasing a final's results
def test_the_inbox_opens_each_waiting_item_in_turn(phone_server):
    import json
    sub = {"id": "s1", "worksheet_id": "w1", "pages": 1, "submitted_at": "2026-11-03T09:00:00Z", "checked_at": None, "score": None,
           "comment": "", "version": 1, "state": "submitted", "note": "שאלה 3?"}
    dana = {**pupil("dana@example.com"), "worksheet_submissions": [sub]}
    entries = [{"kind": "quiz", "class_id": 4, "student_email": "dana@example.com", "title": "מבחן: טכניקה אלגברית 1 · שאלה 2",
                "attempt_id": "a2", "unit_id": "t", "window_id": "win", "submitted_at": "2026-11-02T09:00:00Z", "state": "unreadable", "late": False},
               {"kind": "worksheet", "class_id": 4, "student_email": "dana@example.com", "title": "דף פילוג", "assignment": "חזרה",
                "assignment_id": "asg", "worksheet_id": "w1", "submission_id": "s1", "version": 1, "note": "שאלה 3?",
                "submitted_at": "2026-11-03T09:00:00Z", "state": "submitted", "late": False}]
    saved = []

    def routes(page):
        page.route("**/api/teacher/inbox**", lambda route: route.fulfill(json={"entries": entries, "count": 2, "unavailable": []}))
        page.route("**/api/teacher/answers/a2", lambda route: route.fulfill(json=answer_of("a2")))
        page.route("**/api/teacher/answers/a2/image", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))
        page.route("**/api/teacher/answers/a2/review", lambda route: (saved.append(("a2", json.loads(route.request.post_data))),
                   route.fulfill(json={"review": {"score": 70, "comment": "", "created_at": "2026-11-04T10:00:00Z"}, "request": None}))[1])
        page.route("**/api/classes/4/worksheets/w1/submissions/s1/pages/1", lambda route: route.fulfill(body=PNG, content_type="image/jpeg"))
        page.route("**/api/classes/4/worksheets/w1/submissions/s1", lambda route: (saved.append(("s1", json.loads(route.request.post_data))),
                   route.fulfill(json={**sub, "checked_at": "2026-11-04T10:00:00Z", "score": 90, "state": "checked"}))[1])

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [dana], routes=routes, assignments=[])
        try:
            sheet.locator("[data-report-tab=inbox]").click()
            rows = sheet.locator(".mx-inbox-row")
            playwright.expect(rows).to_have_count(2)
            playwright.expect(rows.nth(0)).to_contain_text("ה־AI לא הצליח לקרוא")                # oldest first
            playwright.expect(rows.nth(1)).to_contain_text('"שאלה 3?"')
            sheet.locator('[data-inbox-filter="kind"]').select_option("worksheet")
            playwright.expect(rows).to_have_count(1)
            sheet.locator('[data-inbox-filter="kind"]').select_option("")
            rows.nth(0).locator("[data-inbox-open]").click()
            review = page.locator(".mx-tr-sheet")
            playwright.expect(review.locator(".mx-tr-ai")).to_contain_text("40/100")
            review.locator("[name=score]").fill("70")
            review.locator("[data-review-form] [type=submit]").click()
            # saved: the next one, Dana's worksheet, opens by itself
            ws = page.locator(".mx-report-sheet .mx-ws-review")
            playwright.expect(ws.locator(".mx-ws-note-shown")).to_contain_text("שאלה 3?")
            ws.locator("[data-ws-check] [name=score]").fill("90")
            ws.locator("[data-ws-check] [type=submit]").click()
            playwright.expect(page.locator(".mx-report-sheet .mx-report")).to_contain_text("סיימתם את כל מה שממתין")
            assert saved == [("a2", {"comment": "", "score": 70}), ("s1", {"score": 90, "comment": ""})]
        finally:
            browser.close()


def test_releasing_a_finals_results_with_open_checks_asks_first(phone_server):
    released = []
    late = {**pupil("noa@example.com"), "quiz_sittings": [{"id": "f2", "unit_id": "t", "mode": "final", "window_id": "win", "grade": None, "open": 1,
                                                         "submitted_at": "2026-11-03T09:00:00Z", "attempts": [], "questions": []}]}
    done = {**pupil("dana@example.com"), "quiz_sittings": [{"id": "f1", "unit_id": "t", "mode": "final", "window_id": "win", "grade": 80, "open": 0,
                                                          "submitted_at": "2026-11-03T09:00:00Z", "attempts": [], "questions": []}]}
    windows = {"windows": [{"id": "win", "class_id": 4, "unit_id": "t", "opens_at": "2026-11-03T08:00:00+00:00",
                            "closes_at": "2026-11-03T10:00:00+00:00", "released_at": None}], "grants": [], "starts": [], "now": "2026-11-04T12:00:00+00:00"}

    def routes(page):
        page.route("**/api/classes/4/quiz-windows", lambda route: route.fulfill(json=windows))
        page.route("**/api/classes/4/quiz-windows/win/release", lambda route: (released.append(1), route.fulfill(json={**windows["windows"][0], "released_at": "x"}))[1])

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [done, late], routes=routes, assignments=[])
        try:
            sheet.locator("[data-report-tab=finals]").click()
            card = sheet.locator(".mx-final-t")
            playwright.expect(card).to_contain_text("הגישו 2 מתוך 2 · נבדקו במלואם 1")
            asked = []
            page.on("dialog", lambda d: (asked.append(d.message), d.accept()))
            card.locator("[data-final-release]").click()
            page.wait_for_timeout(300)
            assert asked and "בוחן אחד עוד לא נבדק" in asked[0] and released == [1]
        finally:
            browser.close()


def test_the_teacher_opens_a_final_quiz_and_gives_one_student_another_sitting(phone_server):
    import json
    posted = []
    windows = {"windows": [], "grants": [], "starts": [], "now": "2026-11-04T12:00:00+00:00"}

    def windows_route(route):
        if route.request.method == "POST":
            body = json.loads(route.request.post_data)
            posted.append(("open", body))
            windows["windows"].append({"id": "win", "class_id": 4, "unit_id": body["unit_id"], "opens_at": body["opens_at"],
                                       "closes_at": body["closes_at"], "released_at": None})
            return route.fulfill(status=201, json=windows["windows"][-1])
        route.fulfill(json=windows)

    def grant_route(route):
        posted.append(("grant", json.loads(route.request.post_data)))
        route.fulfill(status=201, json={"id": "g", "window_id": "win"})

    def routes(page):
        page.route("**/api/classes/4/quiz-windows", windows_route)
        page.route("**/api/classes/4/quiz-windows/win/grants", grant_route)

    with playwright.sync_playwright() as p:
        browser, page, sheet = open_report(p, phone_server, [pupil("dana@example.com")], routes=routes, assignments=[])
        try:
            sheet.locator("[data-report-tab=finals]").click()
            form = sheet.locator("[data-final-open]")
            form.locator("button[type=submit]").click()
            card = sheet.locator(".mx-final-t")
            playwright.expect(card).to_contain_text("טכניקה אלגברית 1")
            kind, body = posted[0]
            assert kind == "open" and body["unit_id"] == "t" and body["opens_at"] < body["closes_at"]
            card.locator("details summary").click()
            card.locator("[data-final-grant] [name=reason]").fill("נעדרה")
            card.locator("[data-final-grant] button[type=submit]").click()
            page.wait_for_timeout(300)
            assert posted[1][0] == "grant" and posted[1][1]["student_email"] == "dana@example.com" and posted[1][1]["reason"] == "נעדרה"
        finally:
            browser.close()


def test_prompter_from_management(phone_server):
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            page.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            page.add_init_script('''window.supabase={createClient:()=>({auth:{
                getSession:async()=>({data:{session:{access_token:"test",user:{id:"test"}}}}),
                onAuthStateChange:()=>{},signOut:async()=>{}
            }})};''')

            def index(route):
                response = route.fetch()
                route.fulfill(response=response, body=response.text().replace(
                    'supabaseUrl:""', 'supabaseUrl:"https://auth.invalid"'))

            page.route(phone_server + "/", index)
            page.route("**/api/me", lambda route: route.fulfill(json={
                "email": "dev@example.com", "user_id": "test", "answer_scans": False,
                "permissions": ["management.access"], "classes": []}))
            page.route("**/api/math/progress", lambda route: route.fulfill(json={"progress": {}}))
            page.route("**/api/classes", lambda route: route.fulfill(json={"classes": []}))
            page.goto(phone_server)
            page.locator('[data-act="manage"]').click()
            page.locator('[data-act="manage-prompter"]').click()
            page.locator("#mxPrompterText").fill("שלום לכולם\nזה טקסט לפרומפטר")
            page.locator('[data-act="prompter-go"]').click()
            prompter = page.locator(".mxp")
            playwright.expect(prompter.locator(".mxp-text")).to_have_text("שלום לכולם\nזה טקסט לפרומפטר")
            page.keyboard.press("m")
            playwright.expect(prompter).to_have_class("mxp mirror")
            page.keyboard.press(" ")
            playwright.expect(prompter).to_have_class("mxp mirror playing", timeout=5000)
            page.keyboard.press("Escape")
            playwright.expect(prompter).to_have_count(0)
            playwright.expect(page.locator(".mx-manage-sheet")).to_be_visible()   # Esc closes only the prompter
        finally:
            browser.close()
