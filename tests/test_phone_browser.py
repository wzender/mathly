"""Optional browser regression checks: pip install playwright && playwright install chromium."""
import base64
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


def test_phone_refresh_upload_and_desktop_network_recovery(phone_server):
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer = browser.new_page()
            computer.route("https://cdn.jsdelivr.net/**", lambda route: route.abort())
            polls = []

            def flaky_network(route):
                polls.append(route.request.url)
                if len(polls) == 1:
                    route.abort()
                else:
                    route.continue_()

            computer.route("**/api/math/photo-sessions/*", flaky_network)
            computer.goto(phone_server)
            computer.locator('[data-act="phone"]').click()
            qr = computer.locator(".mx-phone-qr")
            playwright.expect(qr).to_be_visible()
            assert qr.evaluate("img => img.complete && img.naturalWidth > 0")
            url = computer.locator(".mx-phone-url").input_value()

            # LAN HTTP pages have no Clipboard API. The link must still be selectable.
            computer.evaluate('Object.defineProperty(navigator, "clipboard", {value: undefined})')
            computer.locator('[data-act="copy-phone"]').click()
            playwright.expect(computer.locator(".mx-phone-url")).to_be_focused()

            phone = browser.new_context(is_mobile=True, viewport={"width": 390, "height": 844}).new_page()
            phone.goto(url)
            assert "#" not in phone.url
            phone.reload()
            playwright.expect(phone.locator("#take")).to_be_enabled()
            phone.locator("#camera").set_input_files({"name": "bad.heic", "mimeType": "image/heic", "buffer": b"undecodable"})
            playwright.expect(phone.locator("#status")).to_contain_text("JPEG, PNG")
            playwright.expect(phone.locator("#send")).to_be_hidden()
            # Exercise the fallback used when camera photos cannot use createImageBitmap.
            phone.evaluate("window.createImageBitmap = undefined")
            encoded = computer.evaluate("""() => {
                const canvas = document.createElement('canvas');
                canvas.width = canvas.height = 10;
                return canvas.toDataURL('image/png').split(',')[1];
            }""")
            png = base64.b64decode(encoded)
            phone.locator("#camera").set_input_files({"name": "exercise.png", "mimeType": "image/png", "buffer": png})
            # A proxy can return HTML on failure. Keep the photo ready for another attempt.
            phone.route("**/api/math/phone-photo", lambda route: route.fulfill(status=503, content_type="text/html", body="Unavailable"), times=1)
            phone.locator("#send").click()
            playwright.expect(phone.locator("#status")).to_have_text("לא הצלחנו לשלוח. נסו שוב.")
            playwright.expect(phone.locator("#send")).to_be_enabled()
            phone.locator("#send").click()
            playwright.expect(phone.locator("#status")).to_have_text("הפתרון מוכן במחשב!")
            playwright.expect(computer.locator(".mx-ok")).to_contain_text("10 cm", timeout=10000)
            assert len(polls) >= 2
        finally:
            browser.close()


@pytest.mark.parametrize("manager", [True, False])
def test_class_management_geometry_and_permissions(phone_server, manager):
    import json

    row = {"id": 7, "name": "כיתת תרגול", "lessons": ["t"],
           "emails": ["student@example.com"], "teachers": ["teacher@example.com"],
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
