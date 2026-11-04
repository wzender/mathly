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
            "uq": {"t": {"history": [{"at": "2026-11-03T10:00:00Z", "score": 85}], "going": False}}}},
        {"email": "omer@example.com", "signed_in": False, "saved_at": None, "progress": None}]}
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
            playwright.expect(dana.locator("summary")).to_contain_text("בוחן 85")
            playwright.expect(dana.locator("summary")).to_contain_text("תרגול 9/12")
            playwright.expect(omer).to_contain_text("עוד לא נכנס לחשבון")
            dana.locator("summary").click()
            playwright.expect(dana.locator(".mx-report-table").first).to_contain_text("85/100")
            playwright.expect(dana.locator(".mx-report-table").nth(1)).to_contain_text("75")
            page.locator(".mx-report-sheet .mx-x").click()
            playwright.expect(sheet).to_be_hidden()
        finally:
            browser.close()


def test_class_editor_picks_the_teacher_from_the_students(phone_server):
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
            teacher = page.locator('select[name="teacher"]')
            playwright.expect(teacher).to_have_value("b@example.com")
            assert teacher.locator("option").all_inner_texts() == ["ללא מורה", "a@example.com", "b@example.com"]
            page.locator('textarea[name="emails"]').fill("a@example.com\nb@example.com\nc@example.com")
            playwright.expect(teacher.locator("option")).to_have_count(4)
            playwright.expect(teacher).to_have_value("b@example.com")   # the choice stays while the list grows
            teacher.select_option("c@example.com")
            page.get_by_role("button", name="שמירת השינויים").click()
            playwright.expect(page.locator(".mx-manage-state")).not_to_have_text("שומרים…")
            assert writes[-1]["teachers"] == ["c@example.com"]
            assert writes[-1]["emails"] == ["a@example.com", "b@example.com", "c@example.com"]
        finally:
            browser.close()
