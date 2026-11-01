"""Lesson resources: teachers photograph exercises and explanations for a unit."""
import asyncio
import io
import re
import socket
import threading
import time
import uuid
from pathlib import Path

import httpx
import pytest
import uvicorn
from PIL import Image

from app.main import create_app
from app.unit_resources import UnitResources
from scan_support import BOOTSTRAP, postgres_server

TEACHER = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
COLLEAGUE = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
STUDENT = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'
ADMIN = 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'
ROLES = {TEACHER: ['teacher'], COLLEAGUE: ['teacher'], STUDENT: ['student'], ADMIN: ['admin']}


class Auth:
    url = 'https://test.invalid'
    key = 'public-test'
    secret = 'server-test'
    teachers = frozenset()
    developers = frozenset()

    def user(self, token):
        return {'id': token, 'email': token[:4] + '@test.invalid'} if token in ROLES else None

    def classes(self):
        return []

    def access_for(self, user_id, **_kwargs):
        return {'roles': ROLES[user_id]}


class MemoryResources(UnitResources):
    """The storage calls, kept in memory."""

    def __init__(self):
        super().__init__(Auth())
        self.rows, self.files = {}, {}

    def list(self, unit_id):
        return sorted((r for r in self.rows.values() if r['unit_id'] == unit_id), key=lambda r: r['created_at'], reverse=True)

    def get(self, resource_id):
        return self.rows.get(resource_id)

    def add(self, row):
        row = {**row, 'id': str(uuid.uuid4()), 'created_at': f'2026-11-01T10:{len(self.rows):02d}:00Z'}
        self.rows[row['id']] = row
        return row

    def remove(self, resource_id):
        self.rows.pop(resource_id, None)

    def put(self, key, data):
        self.files[key] = data

    def read(self, key):
        return self.files[key]

    def delete(self, key):
        self.files.pop(key, None)


def png(color='white'):
    out = io.BytesIO()
    Image.new('RGB', (200, 120), color).save(out, 'PNG')
    return out.getvalue()


def app_with(store):
    app = create_app(auth=Auth())
    app.state.resources = store
    return app


def client(app, token):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                             headers={'Authorization': f'Bearer {token}'})


def add(c, unit='t', kind='exercise', note='', skill=''):
    return c.post(f'/api/math/units/{unit}/resources', data={'kind': kind, 'note': note, 'skill': skill},
                  files={'photo': ('p.png', png(), 'image/png')})


def test_teacher_adds_lists_opens_and_deletes_lesson_photos():
    store = MemoryResources()
    app = app_with(store)

    async def check():
        async with client(app, TEACHER) as teacher, client(app, COLLEAGUE) as colleague, \
                client(app, STUDENT) as student, client(app, ADMIN) as admin:
            # an exercise on a topic of the lesson
            saved = await add(teacher, skill='t_ext')
            assert saved.status_code == 201
            first = saved.json()
            assert first['kind'] == 'exercise' and first['skill_id'] == 't_ext' and first['note'] == ''
            assert 'object_key' not in first
            # a theory explanation with no topic, and free text
            assert (await add(teacher, kind='theory')).json()['skill_id'] is None
            other = (await add(teacher, kind='other', note='  סיכום   השיעור  ')).json()
            assert other['note'] == 'סיכום השיעור'
            # what the form refuses
            assert (await add(teacher, kind='photo')).status_code == 400
            assert (await add(teacher, kind='other', note='   ')).status_code == 400
            assert (await add(teacher, kind='other', note='x' * 201)).status_code == 400
            assert (await add(teacher, skill='q_vertex')).status_code == 400   # a topic of another lesson
            assert (await add(teacher, unit='nope')).status_code == 404
            bad = await teacher.post('/api/math/units/t/resources', data={'kind': 'exercise'},
                                     files={'photo': ('p.txt', b'not an image', 'text/plain')})
            assert bad.status_code == 415
            assert len(store.rows) == len(store.files) == 3

            listed = (await colleague.get('/api/math/units/t/resources')).json()['resources']
            assert [r['kind'] for r in listed] == ['other', 'theory', 'exercise']
            assert all('object_key' not in r for r in listed)
            assert (await teacher.get('/api/math/units/t2/resources')).json() == {'resources': []}

            image = await colleague.get(f"/api/math/resources/{first['id']}/image")
            assert image.status_code == 200 and image.headers['content-type'] == 'image/jpeg'
            assert Image.open(io.BytesIO(image.content)).format == 'JPEG'   # re-encoded, metadata dropped
            assert (await teacher.get('/api/math/resources/not-a-uuid/image')).status_code == 404

            # students neither see nor add resources
            assert (await student.get('/api/math/units/t/resources')).status_code == 403
            assert (await add(student)).status_code == 403
            assert (await student.get(f"/api/math/resources/{first['id']}/image")).status_code == 403

            # only the teacher who added a photo, or a manager, deletes it
            assert (await colleague.delete(f"/api/math/resources/{first['id']}")).status_code == 403
            assert (await teacher.delete(f"/api/math/resources/{first['id']}")).json() == {'ok': True}
            assert (await admin.delete(f"/api/math/resources/{other['id']}")).json() == {'ok': True}
            assert (await teacher.delete(f"/api/math/resources/{other['id']}")).status_code == 404
            assert len(store.rows) == len(store.files) == 1

        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as guest:
            assert (await guest.get('/api/math/units/t/resources')).status_code == 401

    asyncio.run(check())
    assert [a['kind'] for a in app.state.actions.recent()].count('resource_added') == 3


def test_resources_fail_closed_without_storage_key():
    store = MemoryResources()
    store.auth = type('NoSecret', (Auth,), {'secret': ''})()
    app = app_with(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            assert (await teacher.get('/api/math/units/t/resources')).status_code == 503
    asyncio.run(check())


def test_migration_keeps_resources_private(postgres_server):
    psycopg = pytest.importorskip('psycopg')
    database = 'res_' + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute('create database ' + database)
    try:
        with psycopg.connect(postgres_server.get_uri(database=database), autocommit=True) as c:
            c.execute(BOOTSTRAP)
            c.execute(Path('supabase/migrations/20261101090000_math_unit_resources.sql').read_text())
            c.execute('insert into auth.users values(%s)', (TEACHER,))
            assert c.execute("select public from storage.buckets where id='mathly-resources'").fetchone()[0] is False
            c.execute("set role service_role")
            c.execute("insert into math_unit_resources(unit_id,kind,skill_id,object_key,byte_size,created_by) "
                      "values('t','exercise','t_ext','t/a.jpg',10,%s)", (TEACHER,))
            for bad in ("('t','other','','t/b.jpg',10)", "('t','photo','','t/c.jpg',10)", "('t','theory','','t/a.jpg',10)"):
                with pytest.raises(psycopg.errors.IntegrityError):
                    c.execute(f"insert into math_unit_resources(unit_id,kind,note,object_key,byte_size) values{bad}")
            c.execute("insert into storage.objects(bucket_id,name) values('mathly-resources','t/a.jpg')")
            c.execute('reset role')
            c.execute('set role authenticated')
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute('select * from math_unit_resources')
            assert c.execute("select count(*) from storage.objects where bucket_id='mathly-resources'").fetchone()[0] == 0
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute('drop database ' + database + ' with (force)')


@pytest.fixture
def resource_server():
    store = MemoryResources()
    app = app_with(store)
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
            yield f'http://127.0.0.1:{sock.getsockname()[1]}', store
        finally:
            server.should_exit = True
            thread.join(timeout=5)


def phone(browser, account):
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
    ctx.route('https://cdn.jsdelivr.net/**', lambda route: route.abort())
    ctx.add_init_script('''window.supabase={createClient:()=>({auth:{
      getSession:async()=>({data:{session:{access_token:'%s',user:{id:'%s'}}}}),
      onAuthStateChange:()=>({data:{subscription:{unsubscribe(){}}}}),signOut:async()=>{}}})};''' % (account, account))
    return ctx.new_page()


def test_teacher_photographs_a_lesson_resource_on_a_phone(resource_server, tmp_path):
    playwright = pytest.importorskip('playwright.sync_api')
    url, store = resource_server
    photo = tmp_path / 'board.png'
    photo.write_bytes(png('lightyellow'))
    expect = playwright.expect
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = phone(browser, TEACHER)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url)
            page.locator('.mx-nav [data-view="path"]').click()
            page.locator('#mx-unit-t .mx-uhead h2').click()   # tapping the lesson's title
            sheet = page.locator('.mx-res')
            expect(sheet.locator('h3')).to_have_text('משאבי השיעור')
            expect(sheet.locator('.mx-uchip')).to_have_text('טכניקה אלגברית 1')
            expect(sheet).to_contain_text('עוד אין משאבים')
            assert page.locator('input[capture="environment"]').count() == 1   # the camera opens directly

            with page.expect_file_chooser() as chooser:
                sheet.locator('[data-act="res-take"]').click()
            chooser.value.set_files(str(photo))
            form = sheet.locator('.mx-res-form')
            expect(form.locator('img.mx-thumb')).to_be_visible()
            form.locator('button[type=submit]').click()
            expect(sheet.locator('.mx-res-msg')).to_contain_text('בחרו מה יש בתמונה')
            assert not store.rows

            form.locator('label', has_text='אחר').click()
            expect(form.locator('input[name=note]')).to_be_visible()
            form.locator('label', has_text='תרגיל חדש').click()
            expect(form.locator('input[name=note]')).to_be_hidden()
            form.locator('select[name=skill]').select_option('t_ext')
            form.locator('button[type=submit]').click()
            expect(sheet.locator('.mx-res-msg')).to_have_text('התמונה נשמרה במשאבי השיעור.')
            item = sheet.locator('.mx-res-item')
            expect(item).to_have_count(1)
            expect(item).to_contain_text('תרגיל חדש')
            expect(item).to_contain_text('פילוג מורחב')
            (row,) = store.rows.values()
            assert (row['unit_id'], row['kind'], row['skill_id']) == ('t', 'exercise', 't_ext')

            # free text, with no topic
            with page.expect_file_chooser() as chooser:
                sheet.locator('[data-act="res-take"]').click()
            chooser.value.set_files(str(photo))
            form.locator('label', has_text='אחר').click()
            form.locator('input[name=note]').fill('דף עבודה לשיעור בית')
            form.locator('button[type=submit]').click()
            expect(item).to_have_count(2)
            expect(item.first).to_contain_text('דף עבודה לשיעור בית')

            # reopening loads the saved photos from the server
            sheet.locator('.mx-x').click()
            page.locator('#mx-unit-t .mx-res-open').click()
            expect(item).to_have_count(2)
            expect(item.last.locator('img')).to_have_attribute('src', re.compile('^blob:'))
            assert errors == []

            student = phone(browser, STUDENT)
            student.goto(url)
            student.locator('.mx-nav [data-view="path"]').click()
            expect(student.locator('#mx-unit-t')).to_be_visible()
            expect(student.locator('.mx-res-open')).to_have_count(0)
            student.locator('#mx-unit-t .mx-uhead h2').click()
            expect(student.locator('.mx-res')).to_have_count(0)
        finally:
            browser.close()
