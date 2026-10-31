"""Desktop/mobile integration against real PostgreSQL and the production API."""
import socket
import threading
import time

import pytest
import uvicorn

from app.main import create_app
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server
from test_answer_scans import png, request

playwright = pytest.importorskip('playwright.sync_api')


@pytest.fixture
def scan_server(answer_store):
    app = create_app(auth=ScanAuth()); app.state.answers = answer_store
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 5
            while not server.started:
                assert thread.is_alive() and time.monotonic() < deadline
                time.sleep(.01)
            yield f'http://127.0.0.1:{sock.getsockname()[1]}', answer_store
        finally:
            server.should_exit = True; thread.join(timeout=5)


def session(browser, owner=OWNER, mobile=False):
    ctx = browser.new_context(viewport={'width': 390 if mobile else 1280, 'height': 844},
                              is_mobile=mobile, has_touch=mobile)
    ctx.route('https://cdn.jsdelivr.net/**', lambda route: route.abort())
    # Stub only the external sign-in SDK; all app APIs and ownership checks run.
    ctx.add_init_script('''window.supabase={createClient:()=>({auth:{
      getSession:async()=>{const id=localStorage.getItem('test.account')||'%s';return {data:{session:{access_token:id,user:{id}}}};},
      onAuthStateChange:cb=>{window.testAuthEvent=cb;return {data:{subscription:{unsubscribe(){}}}};},
      signOut:async()=>window.testAuthEvent('SIGNED_OUT',null)
    }})};''' % owner)
    return ctx


def open_question(page):
    page.locator('.mx-node[data-id="g_triangle_area"]').click()
    playwright.expect(page.locator('.mx-answer')).to_be_visible()
    playwright.expect(page.locator('.mx-choices')).to_have_count(0)


def test_two_device_capture_retake_failure_retry_and_original_attempt(scan_server):
    url, store = scan_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer = session(browser).new_page(); errors=[]
            computer.on('pageerror', lambda error: errors.append(str(error)))
            computer.goto(url)
            with computer.expect_request('**/api/math/answer-attempts') as resume:
                open_question(computer)
            assert len(resume.value.post_data_json['question_version'])==64
            computer.locator('[data-request]').click()
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('ממתינים לטלפון')
            with store.connect() as c:
                attempt_id = str(c.execute('select id from math_question_attempts').fetchone()[0])
            phone = session(browser, mobile=True).new_page()
            phone.on('pageerror', lambda error: errors.append(str(error)))
            request(store, question='another-question')
            phone.goto(url)
            playwright.expect(phone.locator('[data-scan-index]')).to_have_count(2)
            phone.locator('[data-scan-index]').filter(has_text='משולש ישר').click()
            # Confirmation and cancellation do not invoke capture or upload.
            assert phone.locator('[data-camera]').input_value() == ''
            assert phone.locator('[data-take]').is_hidden()
            phone.locator('[data-close]').click()
            phone.locator('[data-scan-index]').filter(has_text='משולש ישר').click()
            phone.evaluate("window.cameraClicks=0;document.addEventListener('click',e=>{if(e.target.matches('[data-camera]'))window.cameraClicks++},true)")
            phone.locator('[data-confirm]').click()
            playwright.expect(phone.locator('[data-take]')).to_be_visible()
            phone.locator('[data-camera]').dispatch_event('cancel')
            playwright.expect(phone.locator('[data-status]')).to_contain_text('לא ניתנה הרשאה')
            image = {'name': 'answer.png', 'mimeType': 'image/png', 'buffer': png()}
            assert phone.evaluate('window.cameraClicks')==0
            with phone.expect_file_chooser() as chooser:
                phone.locator('[data-take]').click()
            chooser.value.set_files(image)
            playwright.expect(phone.locator('[data-submit]')).to_be_visible()
            phone.screenshot(path='/tmp/mathly-answer-phone.png', full_page=True, animations='disabled')
            first = phone.locator('[data-preview]').get_attribute('src')
            phone.locator('[data-camera]').set_input_files(image)
            playwright.expect(phone.locator('[data-preview]')).not_to_have_attribute('src', first)
            assert store.action(OWNER, 'get', attempt_id=attempt_id)['attachment'] is None
            store.fail_put = True
            phone.locator('[data-submit]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('אפשר לנסות שוב')
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('ההעלאה נכשלה', timeout=10000)
            assert phone.locator('[data-preview]').is_visible()
            store.fail_put = False
            started, release = threading.Event(), threading.Event()
            original_put = store.put
            def slow_put(key, data):
                started.set(); assert release.wait(timeout=15); original_put(key, data)
            store.put = slow_put
            phone.locator('[data-submit]').click()
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('מעלים את התשובה…', timeout=10000)
            assert started.is_set()
            computer.locator('.mx-x').click();computer.locator('.mx-node[data-id="g_rectangle"]').click()
            release.set()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('הועלתה בהצלחה', timeout=10000)
            assert computer.locator('.mx-answer-image').count() == 0
            assert computer.locator('.mx-choices button').count() > 0
            computer.locator('.mx-x').click();open_question(computer)
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible()
            assert computer.locator('.mx-answer-image').evaluate('img=>img.complete&&img.naturalWidth>0')
            computer.screenshot(path='/tmp/mathly-answer-computer.png', full_page=True, animations='disabled')
            assert computer.evaluate("!JSON.parse(localStorage.getItem('mathly.progress.v1:'+'%s@test.invalid')||'{}').done?.g_triangle_area" % OWNER)
            computer.reload();open_question(computer)
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible()
            foreign = session(browser, OTHER, mobile=True).new_page();foreign.goto(url)
            playwright.expect(foreign.locator('.mx-scan-inbox')).to_be_empty()
            assert store.action(OWNER, 'get', attempt_id=attempt_id)['attachment']
            assert not errors
        finally:
            browser.close()


def test_expiry_renewal_reconnect_and_account_change(scan_server):
    url, store = scan_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer = session(browser).new_page();computer.goto(url);open_question(computer)
            computer.locator('[data-request]').click()
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('ממתינים לטלפון')
            with store.connect() as c:
                old = str(c.execute('select id from math_answer_scans').fetchone()[0])
                c.execute("update math_answer_scans set expires_at=now()-interval '1 second'")
            computer.route('**/api/math/answer-attempts/*', lambda r:r.abort(), times=1)
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('בקשת הצילום פגה', timeout=15000)
            phone = session(browser, mobile=True).new_page();phone.goto(url)
            phone.locator('[data-scan-index]').click()
            playwright.expect(phone.locator('[data-renew]')).to_be_visible()
            phone.locator('[data-renew]').click()
            playwright.expect(phone.locator('[data-confirm]')).to_be_visible()
            assert store.action(OWNER, 'pending')[0]['scan']['generation'] == 2
            phone.locator('[data-confirm]').click()
            phone.locator('[data-camera]').set_input_files({'name':'answer.png','mimeType':'image/png','buffer':png()})
            phone.locator('[data-submit]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('הועלתה בהצלחה')
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible(timeout=10000)
            # Account change removes the photograph and all old-account continuations.
            computer.evaluate("localStorage.setItem('test.account','%s');window.testAuthEvent('SIGNED_IN',{access_token:'%s',user:{id:'%s'}})" % (OTHER, OTHER, OTHER))
            playwright.expect(computer.locator('.mx-node[data-id="g_triangle_area"]')).to_be_visible()
            assert computer.locator('.mx-answer-image').count() == 0
            open_question(computer)
            playwright.expect(computer.locator('[data-request]')).to_be_enabled()
            assert computer.locator('.mx-answer-image').count() == 0
        finally:
            browser.close()


def test_success_response_loss_is_safe_to_retry(scan_server):
    url, store = scan_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer=session(browser).new_page();computer.goto(url);open_question(computer)
            computer.locator('[data-request]').click()
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('ממתינים לטלפון')
            phone=session(browser,mobile=True).new_page();phone.goto(url)
            phone.locator('[data-scan-index]').click();phone.locator('[data-confirm]').click()
            phone.locator('[data-camera]').set_input_files({'name':'answer.png','mimeType':'image/png','buffer':png()})
            def lost_response(route):
                response=route.fetch()
                assert response.ok
                route.abort()
            phone.route('**/api/math/answer-scans/*/uploads/*',lost_response,times=1)
            phone.locator('[data-submit]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('אפשר לנסות שוב')
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible(timeout=10000)
            phone.locator('[data-submit]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('הועלתה בהצלחה')
            with store.connect() as c:
                assert c.execute('select count(*) from math_answer_attachments').fetchone()[0]==1
            computer.locator('.mx-x').click();computer.locator('.mx-node[data-id="g_rectangle"]').click()
            computer.locator('.mx-choices button[data-m=""]').click()
            assert computer.evaluate("!!JSON.parse(localStorage.getItem('mathly.progress.v1:'+'%s@test.invalid')).done.g_rectangle" % OWNER)
        finally:
            browser.close()
