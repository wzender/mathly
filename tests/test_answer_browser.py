"""Desktop/mobile integration against real PostgreSQL and the production API."""
import socket
import threading
import time

import pytest
import uvicorn

from app.main import create_app
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server
from test_answer_scans import png, request
from test_answer_grading import assessment
from app.answer_grading import validate_assessment
from app.math_photo import PhotoUnavailable

playwright = pytest.importorskip('playwright.sync_api')


@pytest.fixture(autouse=True)
def unlocked_open_ended(monkeypatch):
    """These tests answer the open-ended question, which is locked by default."""
    monkeypatch.setenv('MATHLY_OPEN_ENDED_LOCKED', '0')


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
    page.locator('.mx-nav [data-view="path"]').click()   # the app opens on the home screen
    page.locator('.mx-node[data-id="a_30_side"]').click()
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
            # no window over the question: the button itself shows the 4-digit code and the progress
            wait = computer.locator('.mx-answer .mx-phone-live')
            playwright.expect(wait).to_contain_text('ממתינים לטלפון')
            playwright.expect(wait.locator('.mx-scan-code span')).to_have_count(4)
            assert computer.locator('.mx-scan-overlay').count() == 0
            playwright.expect(computer.locator('.mx-answer')).to_be_visible()   # the question stays in view
            code = wait.locator('.mx-scan-code').inner_text().replace('\n', '')
            assert len(code) == 4 and code.isdigit()
            with store.connect() as c:
                attempt_id = str(c.execute('select id from math_question_attempts').fetchone()[0])
            phone = session(browser, mobile=True).new_page()
            phone.on('pageerror', lambda error: errors.append(str(error)))
            other = request(store, question='another-question')
            phone.goto(url)
            # the newest request pops up first, as a window; declining it leaves the other one
            ask = phone.locator('.mx-scan-overlay')
            playwright.expect(ask).to_contain_text('Draw your proof')
            phone.locator('[data-decline]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('סירבתם')
            assert store.action(OWNER, 'get', scan_id=other['scan']['id'])['scan']['state'] == 'declined'
            phone.locator('[data-close]').click()
            playwright.expect(ask).to_contain_text('משולש ישר', timeout=10000)
            # the phone shows the same code as the computer
            assert ask.locator('.mx-scan-code').inner_text().replace('\n', '') == code
            phone.locator('[data-camera]').dispatch_event('cancel')
            playwright.expect(phone.locator('[data-status]')).to_contain_text('לא ניתנה הרשאה')
            image = {'name': 'answer.png', 'mimeType': 'image/png', 'buffer': png()}
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
            playwright.expect(wait).to_contain_text('ההעלאה נכשלה', timeout=10000)
            assert phone.locator('[data-preview]').is_visible()
            store.fail_put = False
            started, release = threading.Event(), threading.Event()
            original_put = store.put
            def slow_put(key, data):
                started.set(); assert release.wait(timeout=15); original_put(key, data)
            store.put = slow_put
            phone.locator('[data-submit]').click()
            playwright.expect(wait).to_contain_text('מקבלים את התמונה מהטלפון', timeout=10000)
            assert started.is_set()
            release.set()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('נשלחה למחשב', timeout=10000)
            playwright.expect(wait).to_have_count(0, timeout=10000)   # the code box gives way to the photo
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible()
            assert computer.locator('.mx-answer-image').evaluate('img=>img.complete&&img.naturalWidth>0')
            computer.screenshot(path='/tmp/mathly-answer-computer.png', full_page=True, animations='disabled')
            assert computer.evaluate("!JSON.parse(localStorage.getItem('mathly.progress.v1:'+'%s@test.invalid')||'{}').done?.a_30_side" % OWNER)
            computer.reload();open_question(computer)
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible()
            foreign = session(browser, OTHER, mobile=True).new_page();foreign.goto(url)
            foreign.wait_for_timeout(1500)
            playwright.expect(foreign.locator('.mx-scan-overlay')).to_have_count(0)
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
            playwright.expect(computer.locator('.mx-phone-live')).to_contain_text('ממתינים לטלפון')
            with store.connect() as c:
                old = str(c.execute('select id from math_answer_scans').fetchone()[0])
                c.execute("update math_answer_scans set expires_at=now()-interval '1 second'")
            computer.route('**/api/math/answer-attempts/*', lambda r:r.abort(), times=1)
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('בקשת הצילום פגה', timeout=15000)
            playwright.expect(computer.locator('.mx-phone-live')).to_have_count(0)
            playwright.expect(computer.locator('[data-request]')).to_contain_text('בקשת צילום חדשה')
            phone = session(browser, mobile=True).new_page();phone.goto(url)
            phone.wait_for_timeout(1500)
            playwright.expect(phone.locator('.mx-scan-overlay')).to_have_count(0)   # an expired request does not pop up
            computer.locator('[data-request]').click()
            playwright.expect(phone.locator('.mx-scan-overlay')).to_be_visible(timeout=10000)
            assert store.action(OWNER, 'pending')[0]['scan']['generation'] == 2
            phone.locator('[data-camera]').set_input_files({'name':'answer.png','mimeType':'image/png','buffer':png()})
            phone.locator('[data-submit]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('נשלחה למחשב')
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible(timeout=10000)
            # Account change removes the photograph and all old-account continuations.
            computer.evaluate("localStorage.setItem('test.account','%s');window.testAuthEvent('SIGNED_IN',{access_token:'%s',user:{id:'%s'}})" % (OTHER, OTHER, OTHER))
            playwright.expect(computer.locator('.mx-node[data-id="a_30_side"]')).to_be_visible()
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
            playwright.expect(computer.locator('.mx-phone-live')).to_contain_text('ממתינים לטלפון')
            phone=session(browser,mobile=True).new_page();phone.goto(url)
            playwright.expect(phone.locator('.mx-scan-overlay')).to_be_visible()
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
            playwright.expect(phone.locator('[data-status]')).to_contain_text('נשלחה למחשב')
            with store.connect() as c:
                assert c.execute('select count(*) from math_answer_attachments').fetchone()[0]==1
            computer.locator('.mx-x').click();computer.locator('.mx-node[data-id="m_def"]').click()
            computer.locator('.mx-choices button[data-m=""]').click()
            # one right answer of ten is recorded, but does not finish the skill
            assert computer.evaluate("JSON.parse(localStorage.getItem('mathly.progress.v1:'+'%s@test.invalid')).solved.m_def.length===1" % OWNER)
        finally:
            browser.close()


@pytest.mark.parametrize('verdict', ['correct', 'partial', 'incorrect', 'unreadable', 'needs_review'])
def test_check_feedback_progress_reload_and_retake(scan_server, monkeypatch, verdict):
    url, store = scan_server
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'browser-test-key')
    calls = []
    started, release = threading.Event(), threading.Event()
    class Grader:
        def __init__(self, key):
            pass
        def grade(self, image, snapshot):
            calls.append(snapshot)
            if len(calls) == 1:
                raise PhotoUnavailable('temporary failure')
            started.set(); assert release.wait(timeout=15)
            changes = {'correct': {}, 'partial': {'complete': False, 'score': 60},
                       'incorrect': {'answer_correct': False, 'score': 0},
                       'unreadable': {'readable': False}, 'needs_review': {'confident': False}}[verdict]
            # Verify that model text is escaped before rendering.
            return validate_assessment(assessment(feedback='משוב <script>bad()</script> על הפתרון', **changes))
    monkeypatch.setattr('app.answer_routes.AnswerGrader', Grader)
    from test_answer_scans import begin, finish
    from app.math_skills import algebra9, question_version
    skill = next(s for s in algebra9()['skills'] if s['id'] == 'a_30_side')
    done = store.action(OWNER, 'resume', question_id=skill['id'],
                        question_version=question_version(skill['sample']), snapshot=skill['sample'])
    done = finish(store, begin(store, store.action(OWNER, 'create_scan', attempt_id=done['attempt']['id'])))
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer = session(browser).new_page(); errors=[]
            computer.on('pageerror', lambda error: errors.append(str(error)))
            computer.goto(url); open_question(computer)
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible()
            # Opening a received answer starts its first check automatically.
            playwright.expect(computer.locator('[data-grade]')).to_have_text('ניסיון בדיקה נוסף')
            computer.locator('[data-grade]').click()
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('בודקים את התשובה…')
            assert started.wait(timeout=5)
            playwright.expect(computer.locator('[data-new-attempt]')).to_be_disabled()
            release.set()
            panel = computer.locator('.mx-grade')
            playwright.expect(panel).to_be_visible(timeout=10000)
            playwright.expect(panel).to_contain_text('<script>bad()</script>')
            assert panel.locator('script').count() == 0
            if verdict in ('unreadable', 'needs_review'):
                assert '/100' not in panel.inner_text()
            key = 'mathly.progress.v1:' + OWNER + '@test.invalid'
            assert computer.evaluate("key=>!!JSON.parse(localStorage.getItem(key)||'{}').done?.a_30_side", key) == (verdict == 'correct')
            computer.reload();open_question(computer)
            playwright.expect(computer.locator('.mx-grade')).to_be_visible()
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible()
            assert len(calls) == 2
            computer.locator('[data-new-attempt]').click()
            playwright.expect(computer.locator('[data-request]')).to_be_enabled()
            assert computer.locator('.mx-grade').count() == 0
            assert computer.locator('.mx-answer-image').count() == 0
            # The old attempt, photograph, and grade remain recoverable.
            assert store.grade(OWNER, 'get', attempt_id=done['attempt']['id'])['result']['verdict'] == verdict
            assert store.read(done['attachment']['object_key'])
            assert not errors
        finally:
            release.set(); browser.close()


def test_upload_is_acknowledged_before_automatic_grading_finishes(scan_server, monkeypatch):
    url, store = scan_server
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'browser-test-key')
    started, release = threading.Event(), threading.Event()
    calls=[]
    class Grader:
        def __init__(self, key): pass
        def grade(self, image, snapshot):
            calls.append(snapshot);started.set()
            assert release.wait(timeout=20)
            return validate_assessment(assessment())
    monkeypatch.setattr('app.answer_routes.AnswerGrader', Grader)
    with playwright.sync_playwright() as p:
        browser=p.chromium.launch()
        try:
            computer=session(browser).new_page();computer.goto(url);open_question(computer)
            computer.locator('[data-request]').click()
            playwright.expect(computer.locator('.mx-phone-live')).to_contain_text('ממתינים לטלפון')
            phone=session(browser,mobile=True).new_page();phone.goto(url)
            playwright.expect(phone.locator('.mx-scan-overlay')).to_be_visible()
            phone.locator('[data-camera]').set_input_files({'name':'answer.png','mimeType':'image/png','buffer':png()})
            playwright.expect(phone.locator('.mx-scan-card')).to_contain_text('יישלח לבדיקה באמצעות AI')
            phone.locator('[data-submit]').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('נשלחה למחשב')
            assert started.wait(timeout=5)
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('בודקים את התשובה…')
            assert len(calls)==1
            release.set()
            playwright.expect(computer.locator('.mx-grade')).to_contain_text('100/100',timeout=10000)
            assert len(calls)==1
        finally:
            release.set();browser.close()


def test_phone_declines_and_computer_withdraws(scan_server):
    url, store = scan_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer = session(browser).new_page(); errors = []
            computer.on('pageerror', lambda error: errors.append(str(error)))
            computer.goto(url); open_question(computer)
            computer.locator('[data-request]').click()
            wait = computer.locator('.mx-phone-live')
            playwright.expect(wait.locator('.mx-scan-code span')).to_have_count(4)
            phone = session(browser, mobile=True).new_page()
            phone.on('pageerror', lambda error: errors.append(str(error)))
            phone.goto(url)
            # the phone declines: the computer reports it
            phone.locator('[data-decline]').click()
            playwright.expect(computer.locator('.mx-answer [role=status]')).to_have_text('הבקשה נדחתה בטלפון', timeout=10000)
            playwright.expect(wait).to_have_count(0)
            phone.locator('[data-close]').click()
            # a new request pops up again; the computer withdraws it and the phone's window says so
            computer.locator('[data-request]').click()
            playwright.expect(phone.locator('.mx-scan-overlay [data-take]')).to_be_visible(timeout=10000)
            computer.locator('[data-cancel-scan]').click()
            playwright.expect(wait).to_have_count(0)
            playwright.expect(phone.locator('[data-status]')).to_contain_text('בוטלה במחשב', timeout=10000)
            assert store.action(OWNER, 'pending') == []
            assert not errors
        finally:
            browser.close()


def test_phone_asks_once_for_notifications_and_the_bell_toggles(answer_store, monkeypatch):
    """The phone asks once (אישור / לא, תודה); the 🔔 in the top bar turns notifications on and off later.
    The browser's push service is stubbed: only the page's choices and what it sends the server are checked."""
    from app.push import new_private_key
    monkeypatch.setenv('VAPID_PRIVATE_KEY', new_private_key())
    app = create_app(auth=ScanAuth()); app.state.answers = answer_store
    saved = {}

    class Push:   # the stored subscriptions, without Supabase
        on, public, why = True, '', ''
        def save(self, user, sub): saved[sub['endpoint']] = user
        def delete(self, endpoint, user=None): saved.pop(endpoint, None)
        def scan_requested(self, *a): return 0
    app.state.push = Push()
    from app.push import public_key
    import os
    app.state.push.public = public_key(os.environ['VAPID_PRIVATE_KEY'])
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True); thread.start()
        while not server.started: time.sleep(.01)
        url = f'http://127.0.0.1:{sock.getsockname()[1]}'
        stub = '''(()=>{let perm=localStorage.getItem('test.perm')||'default',sub=null;
          Object.defineProperty(window,'Notification',{value:{get permission(){return perm;},
            requestPermission:async()=>(perm=localStorage.getItem('test.answer')||'granted')}});
          const mk=()=>({endpoint:'https://push.test/'+Math.random(),toJSON(){return {endpoint:this.endpoint,keys:{p256dh:'p',auth:'a'}};},
            unsubscribe:async()=>{sub=null;return true;}});
          window.PushManager=function(){};
          const reg={pushManager:{getSubscription:async()=>sub,subscribe:async()=>(sub=mk())},getNotifications:async()=>[]};
          Object.defineProperty(navigator,'serviceWorker',{value:{register:async()=>reg,ready:Promise.resolve(reg),
            getRegistration:async()=>reg,addEventListener(){}}});})();'''
        with playwright.sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                ctx = session(browser, mobile=True); ctx.add_init_script(stub)
                phone = ctx.new_page(); errors = []
                phone.on('pageerror', lambda error: errors.append(str(error)))
                phone.goto(url)
                ask = phone.locator('.mx-push-ask')
                playwright.expect(ask).to_contain_text('התראות מהמחשב')
                ask.get_by_role('button', name='לא, תודה').click()
                playwright.expect(ask).to_have_count(0)
                bell = phone.locator('.mx-push-btn').first
                playwright.expect(bell).to_have_text('🔕')
                assert not saved
                phone.reload()   # asked once: not again
                playwright.expect(bell).to_have_text('🔕')
                phone.wait_for_timeout(500); playwright.expect(ask).to_have_count(0)
                bell.click()
                phone.locator('.mx-push-ask').get_by_role('button', name='אישור').click()
                playwright.expect(bell).to_have_text('🔔')
                assert list(saved.values()) == [OWNER]
                bell.click()
                phone.locator('.mx-push-ask').get_by_role('button', name='כיבוי').click()
                playwright.expect(bell).to_have_text('🔕')
                assert not saved
                # a refusal in the browser's own question: the window says so, and the bell then explains the block
                phone.evaluate("localStorage.setItem('test.answer','denied')")
                bell.click()
                phone.locator('.mx-push-ask').get_by_role('button', name='אישור').click()
                playwright.expect(phone.locator('.mx-push-ask')).to_contain_text('נחסמו')
                phone.locator('.mx-push-ask').get_by_role('button', name='ביטול').click()
                playwright.expect(bell).to_have_text('🔕')
                assert errors == []
                # a computer never shows the bell
                computer = session(browser).new_page(); computer.goto(url)
                playwright.expect(computer.locator('.mx-acts').first).to_be_visible()
                assert computer.locator('.mx-push-btn:visible').count() == 0
            finally:
                browser.close(); server.should_exit = True; thread.join(timeout=5)


def test_the_phone_answers_a_photo_request_by_drawing_on_the_board(scan_server):
    url, store = scan_server
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            computer = session(browser).new_page(); errors = []
            computer.on('pageerror', lambda error: errors.append(str(error)))
            computer.goto(url)
            open_question(computer)
            computer.locator('[data-request]').click()
            wait = computer.locator('.mx-answer .mx-phone-live')
            playwright.expect(wait).to_contain_text('ממתינים לטלפון')
            phone = session(browser, mobile=True).new_page()
            phone.on('pageerror', lambda error: errors.append(str(error)))
            phone.goto(url)
            ask = phone.locator('.mx-scan-overlay')
            playwright.expect(ask).to_contain_text('משולש ישר', timeout=10000)
            phone.locator('[data-draw]').click()   # the board instead of a photo
            board = phone.locator('.mx-board.full')
            playwright.expect(board).to_be_visible()
            box = board.locator('canvas').bounding_box()
            assert box['width'] > 300 and box['height'] > 500   # the whole phone screen
            phone.locator('.mx-board-send').click()   # nothing drawn yet: nothing is sent
            playwright.expect(phone.locator('.mx-board-send')).to_contain_text('הלוח ריק')
            phone.locator('.mx-board [data-do=question]').click()   # the question, copied to the top
            phone.locator('.mx-board [data-tool=pen]').click()
            x, y = box['x'] + 60, box['y'] + 300
            phone.mouse.move(x, y); phone.mouse.down()
            for k in range(1, 12):
                phone.mouse.move(x + k * 20, y + (k % 3) * 15)
            phone.mouse.up()
            phone.wait_for_timeout(2600)
            phone.locator('.mx-board-send').click()
            playwright.expect(phone.locator('[data-status]')).to_contain_text('נשלחה למחשב', timeout=10000)
            playwright.expect(board).to_have_count(0, timeout=5000)   # back to the request's window
            playwright.expect(computer.locator('.mx-answer-image')).to_be_visible(timeout=10000)
            with store.connect() as c:
                attempt_id = str(c.execute('select id from math_question_attempts').fetchone()[0])
            assert store.action(OWNER, 'get', attempt_id=attempt_id)['attachment']
            assert not errors
        finally:
            browser.close()
