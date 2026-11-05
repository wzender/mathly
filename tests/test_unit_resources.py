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
ROLES = {TEACHER: ['teacher'], COLLEAGUE: ['teacher'], STUDENT: ['student'], ADMIN: ['developer']}   # managers are developers


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

    def set_visible(self, resource_id, visible):
        if resource_id in self.rows:
            self.rows[resource_id]['visible'] = visible
        return self.rows.get(resource_id)

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


# ---- what students see
def classed(*students_in_class_t):
    """An Auth with one class that has unit t, for the students listed; the others are in no class."""
    class ClassedAuth(Auth):
        def classes(self):
            return [{'id': 1, 'name': 'ט1', 'lessons': ['t'], 'emails': [s[:4] + '@test.invalid' for s in students_in_class_t],
                     'teachers': [], 'nicknames': {}, 'exams': []}]
    return ClassedAuth()


def test_the_migration_adds_a_visible_column_that_starts_false(postgres_server):
    psycopg = pytest.importorskip('psycopg')
    database = 'resvis_' + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute('create database ' + database)
    try:
        with psycopg.connect(postgres_server.get_uri(database=database), autocommit=True) as c:
            c.execute(BOOTSTRAP)
            c.execute(Path('supabase/migrations/20261101090000_math_unit_resources.sql').read_text())
            c.execute('insert into auth.users values(%s)', (TEACHER,))
            c.execute("insert into math_unit_resources(unit_id,kind,object_key,byte_size) values('t','theory','t/old.jpg',10)")
            c.execute(Path('supabase/migrations/20261104180000_math_resources_visible.sql').read_text())
            c.execute("insert into math_unit_resources(unit_id,kind,object_key,byte_size) values('t','exercise','t/new.jpg',10)")
            c.execute("insert into math_unit_resources(unit_id,kind,object_key,byte_size,visible) values('t','theory','t/shown.jpg',10,true)")
            rows = dict(c.execute('select object_key, visible from math_unit_resources').fetchall())
            assert rows == {'t/old.jpg': False, 't/new.jpg': False, 't/shown.jpg': True}   # what existed stays hidden
            assert c.execute("select is_nullable from information_schema.columns where table_name='math_unit_resources' "
                             "and column_name='visible'").fetchone()[0] == 'NO'
            c.execute('set role authenticated')
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute('select visible from math_unit_resources')
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute('drop database ' + database + ' with (force)')


def test_a_resource_is_visible_by_default_only_when_it_is_a_theory_explanation():
    store = MemoryResources()
    app = app_with(store)

    async def check():
        async with client(app, TEACHER) as teacher:
            made = {k: (await add(teacher, kind=k, note='הערה')).json() for k in ('exercise', 'theory', 'other')}
            assert [made[k]['visible'] for k in ('exercise', 'theory', 'other')] == [False, True, False]
            on = (await teacher.post('/api/math/units/t/resources', data={'kind': 'exercise', 'visible': '1'},
                                     files={'photo': ('p.png', png(), 'image/png')})).json()
            off = (await teacher.post('/api/math/units/t/resources', data={'kind': 'theory', 'visible': '0'},
                                      files={'photo': ('p.png', png(), 'image/png')})).json()
            assert (on['visible'], off['visible']) == (True, False)               # the form's box wins over the default
            listed = (await teacher.get('/api/math/units/t/resources')).json()['resources']
            assert {r['id']: r['visible'] for r in listed} == {made['exercise']['id']: False, made['theory']['id']: True,
                                                              made['other']['id']: False, on['id']: True, off['id']: False}
    asyncio.run(check())


def test_only_the_teacher_who_added_a_resource_or_a_manager_changes_who_sees_it():
    store = MemoryResources()
    app = app_with(store)

    async def check():
        async with client(app, TEACHER) as teacher, client(app, COLLEAGUE) as colleague, \
                client(app, STUDENT) as student, client(app, ADMIN) as admin:
            rid = (await add(teacher)).json()['id']
            patch = lambda c, **body: c.patch(f'/api/math/resources/{rid}', json=body)
            assert (await patch(colleague, visible=True)).status_code == 403
            assert (await patch(student, visible=True)).status_code == 403
            assert store.rows[rid]['visible'] is False                         # still hidden
            shown = await patch(teacher, visible=True)
            assert shown.status_code == 200 and shown.json()['visible'] is True and 'object_key' not in shown.json()
            assert (await patch(admin, visible=False)).json()['visible'] is False
            for bad in ({}, {'visible': 'yes'}, {'visible': 1}, {'visible': None}):
                assert (await patch(teacher, **bad)).status_code == 400
            assert (await teacher.patch(f'/api/math/resources/{uuid.uuid4()}', json={'visible': True})).status_code == 404
            assert (await teacher.patch('/api/math/resources/not-a-uuid', json={'visible': True})).status_code == 404
    asyncio.run(check())


def test_students_see_only_the_visible_resources_of_their_classs_units():
    store = MemoryResources()
    app = create_app(auth=classed(STUDENT))
    app.state.resources = store

    async def check():
        async with client(app, TEACHER) as teacher, client(app, STUDENT) as student, client(app, COLLEAGUE) as colleague:
            shown = (await add(teacher, kind='theory', skill='t_ext')).json()
            hidden = (await add(teacher, kind='exercise')).json()
            other_unit = (await add(teacher, unit='k', kind='theory')).json()   # t2 would come with t: it was split off from it
            assert shown['visible'] and not hidden['visible']
            listed = await student.get('/api/math/units/t/student-resources')
            assert listed.status_code == 200
            rows = listed.json()['resources']
            assert [r['id'] for r in rows] == [shown['id']] and rows[0]['skill_id'] == 't_ext'
            assert set(rows[0]) == {'id', 'unit_id', 'kind', 'note', 'skill_id', 'created_at'}   # no teacher, no storage path
            assert 'test.invalid' not in listed.text and 'object_key' not in listed.text
            image = await student.get(f"/api/math/student-resources/{shown['id']}/image")
            assert image.status_code == 200 and image.headers['content-type'] == 'image/jpeg'
            assert image.headers['cache-control'].startswith('private')
            # a hidden resource, asked for by its id, is not found
            assert (await student.get(f"/api/math/student-resources/{hidden['id']}/image")).status_code == 404
            # a unit their class does not have
            assert (await student.get('/api/math/units/k/student-resources')).status_code == 404
            assert (await student.get(f"/api/math/student-resources/{other_unit['id']}/image")).status_code == 404
            assert (await student.get('/api/math/units/nope/student-resources')).status_code == 404
            assert (await student.get('/api/math/student-resources/not-a-uuid/image')).status_code == 404
            # the teacher's own list still has all of them, each marked
            assert len((await teacher.get('/api/math/units/t/resources')).json()['resources']) == 2
            # hiding it again takes it away from the student at once
            await teacher.patch(f"/api/math/resources/{shown['id']}", json={'visible': False})
            assert (await student.get('/api/math/units/t/student-resources')).json() == {'resources': []}
            assert (await student.get(f"/api/math/student-resources/{shown['id']}/image")).status_code == 404
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as guest:
            assert (await guest.get('/api/math/units/t/student-resources')).status_code == 401
    asyncio.run(check())


def test_without_any_class_every_unit_is_open_to_students():
    store = MemoryResources()
    app = app_with(store)   # no classes configured: the whole path is open

    async def check():
        async with client(app, TEACHER) as teacher, client(app, STUDENT) as student:
            await add(teacher, unit='t2', kind='theory')
            assert len((await student.get('/api/math/units/t2/student-resources')).json()['resources']) == 1
    asyncio.run(check())


def jpeg(color='white'):
    out = io.BytesIO()
    Image.new('RGB', (200, 120), color).save(out, 'JPEG')
    return out.getvalue()


def seed(store, kind='theory', skill=None, note='', visible=True, unit='t', owner=TEACHER):
    key = f'{unit}/{uuid.uuid4()}.jpg'
    store.put(key, jpeg())
    return store.add({'unit_id': unit, 'kind': kind, 'note': note, 'skill_id': skill, 'object_key': key, 'byte_size': 10,
                      'created_by': owner, 'created_email': 'aaaa@test.invalid', 'visible': visible})


def test_the_teacher_decides_what_students_see_with_a_box_and_a_toggle(resource_server, tmp_path):
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
            page.locator('#mx-unit-t .mx-uhead h2').click()
            sheet = page.locator('.mx-res')

            def take(kind):
                with page.expect_file_chooser() as chooser:
                    sheet.locator('[data-act="res-take"]').click()
                chooser.value.set_files(str(photo))
                form = sheet.locator('.mx-res-form')
                form.locator('label', has_text=kind).click()
                return form

            # the box follows the kind until the teacher decides
            form = take('הסבר תיאורטי')
            box = form.locator('input[name=visible]')
            expect(box).to_be_checked()
            form.locator('label', has_text='תרגיל חדש').click()
            expect(box).not_to_be_checked()
            form.locator('label', has_text='הסבר תיאורטי').click()
            expect(box).to_be_checked()
            form.locator('label', has_text='תרגיל חדש').click()
            box.check()                                                           # an exercise the teacher wants shown
            form.locator('label', has_text='הסבר תיאורטי').click()
            expect(box).to_be_checked()                                           # a decision is not overridden
            form.locator('label', has_text='תרגיל חדש').click()
            expect(box).to_be_checked()
            form.locator('button[type=submit]').click()
            expect(sheet.locator('.mx-res-item')).to_have_count(1)
            expect(sheet.locator('.mx-res-vis')).to_have_text('👁 גלוי לתלמידים')
            # a theory explanation is shown without touching the box; an exercise left alone stays hidden
            form = take('הסבר תיאורטי')
            form.locator('button[type=submit]').click()
            form = take('תרגיל חדש')
            expect(form.locator('input[name=visible]')).not_to_be_checked()
            form.locator('button[type=submit]').click()
            expect(sheet.locator('.mx-res-item')).to_have_count(3)
            assert sorted(r['visible'] for r in store.rows.values()) == [False, True, True]
            hidden = sheet.locator('.mx-res-item', has=page.locator('.mx-res-vis:not(.on)'))
            expect(hidden).to_have_count(1)
            hidden.locator('[data-act=res-visible]').click()
            expect(sheet.locator('.mx-res-msg')).to_have_text('התמונה גלויה עכשיו לתלמידים.')
            assert [r['visible'] for r in store.rows.values()].count(True) == 3
            expect(sheet.locator('.mx-res-vis.on')).to_have_count(3)
            sheet.locator('.mx-res-item').first.locator('[data-act=res-visible]').click()
            expect(sheet.locator('.mx-res-msg')).to_have_text('התמונה מוסתרת מהתלמידים.')
            expect(sheet.locator('.mx-res-vis.on')).to_have_count(2)
            # a colleague sees which are shown, but cannot change them
            colleague = phone(browser, COLLEAGUE)
            colleague.goto(url)
            colleague.locator('.mx-nav [data-view="path"]').click()
            colleague.locator('#mx-unit-t .mx-uhead h2').click()
            other = colleague.locator('.mx-res')
            expect(other.locator('.mx-res-item')).to_have_count(3)
            expect(other.locator('.mx-res-vis')).to_have_count(3)
            expect(other.locator('[data-act=res-visible]')).to_have_count(0)
            assert errors == []
        finally:
            browser.close()


def test_a_student_finds_the_teachers_explanations_in_the_skill_its_help_and_the_unit(resource_server):
    playwright = pytest.importorskip('playwright.sync_api')
    url, store = resource_server
    expect = playwright.expect
    seed(store, kind='theory', skill='t_ext', note='')                  # for the skill
    seed(store, kind='other', note='סיכום היחידה', visible=True)         # for the whole unit
    seed(store, kind='exercise', skill='t_ext', visible=False)          # hidden
    seed(store, kind='theory', skill='t_simplify', visible=False)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = phone(browser, STUDENT)
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url)
            page.locator('.mx-nav [data-view="path"]').click()
            # the skill's sheet: the explanation tagged with it, and only that one
            page.locator('.mx-star[data-id="t_ext"]').click()
            box = page.locator('.mx-sheet [data-skill-res]')
            expect(box).to_be_visible()
            expect(box.locator('h4')).to_have_text('הסברים מהמורה')
            expect(box.locator('figure')).to_have_count(1)
            expect(box.locator('figure img')).to_have_attribute('src', re.compile('^blob:'))
            expect(box.locator('figcaption')).to_contain_text('הסבר תיאורטי')
            # its help panel shows it too
            page.locator('.mx-helpbtn').click()
            expect(page.locator('.mx-help [data-help-resources] figure')).to_have_count(1)
            expect(page.locator('.mx-help [data-help-resources] img')).to_have_attribute('src', re.compile('^blob:'))
            page.locator('.mx-help button.solid').click()
            page.locator('.mx-sheet .mx-x').last.click()
            # a skill with none visible shows no such box
            page.locator('.mx-star[data-id="t_simplify"]').click()
            expect(page.locator('.mx-sheet [data-skill-res]')).to_be_hidden()
            page.locator('.mx-sheet .mx-x').last.click()
            # the unit's own: a button under the unit, then the list
            button = page.locator('#mx-unit-t .mx-sres-open')
            expect(button).to_have_text('📷 הסברים מהמורה (1)')
            button.click()
            listed = page.locator('.mx-res [data-unit-res]')
            expect(listed.locator('figure')).to_have_count(1)
            expect(listed.locator('figcaption')).to_contain_text('סיכום היחידה')
            listed.locator('.mx-sres-img').click()                                # tap to enlarge
            expect(listed.locator('.mx-sres-item.zoom')).to_have_count(1)
            assert errors == []
        finally:
            browser.close()


def test_a_unit_without_explanations_for_the_unit_has_no_button(resource_server):
    playwright = pytest.importorskip('playwright.sync_api')
    url, store = resource_server
    seed(store, kind='theory', skill='t_ext')                           # tied to a skill only
    seed(store, kind='other', note='מוסתר', visible=False)
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = phone(browser, STUDENT)
            page.goto(url)
            page.locator('.mx-nav [data-view="path"]').click()
            playwright.expect(page.locator('#mx-unit-t')).to_be_visible()
            page.wait_for_timeout(800)
            assert page.locator('.mx-sres-open').count() == 0
        finally:
            browser.close()


@pytest.fixture
def class_server():
    """The app with one class (unit t) that the student is in, and the resources kept in memory."""
    store = MemoryResources()
    app = create_app(auth=classed(STUDENT))
    app.state.resources = store
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


def test_a_theory_photo_a_teacher_uploads_appears_in_their_students_skill_sheet(class_server, tmp_path):
    """The whole path in two browsers: the teacher photographs a theory explanation of a skill, and the student of the
    class, opening that skill, finds it under the teacher's explanations."""
    playwright = pytest.importorskip('playwright.sync_api')
    url, store = class_server
    photo = tmp_path / 'board.png'
    photo.write_bytes(png('lightyellow'))
    expect = playwright.expect
    with playwright.sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            teacher = phone(browser, TEACHER)
            teacher.goto(url)
            teacher.locator('.mx-nav [data-view="path"]').click()
            teacher.locator('#mx-unit-t .mx-uhead h2').click()
            sheet = teacher.locator('.mx-res')
            with teacher.expect_file_chooser() as chooser:
                sheet.locator('[data-act="res-take"]').click()
            chooser.value.set_files(str(photo))
            form = sheet.locator('.mx-res-form')
            form.locator('label', has_text='הסבר תיאורטי').click()
            form.locator('select[name=skill]').select_option('t_ext')
            form.locator('button[type=submit]').click()
            expect(sheet.locator('.mx-res-vis')).to_have_text('👁 גלוי לתלמידים')
            (row,) = store.rows.values()
            assert (row['kind'], row['skill_id'], row['visible']) == ('theory', 't_ext', True)

            student = phone(browser, STUDENT)
            errors = []
            student.on('pageerror', lambda error: errors.append(str(error)))
            student.goto(url)
            student.locator('.mx-nav [data-view="path"]').click()
            student.locator('.mx-star[data-id="t_ext"]').click()
            box = student.locator('.mx-sheet [data-skill-res]')
            expect(box).to_be_visible()
            expect(box.locator('figure')).to_have_count(1)
            expect(box.locator('figure img')).to_have_attribute('src', re.compile('^blob:'))
            assert errors == []
            # the teacher hides it: the student no longer finds it (after the page asks again)
            teacher.locator('.mx-res [data-act=res-visible]').click()
            expect(teacher.locator('.mx-res-vis')).to_have_text('🔒 מוסתר מהתלמידים')
            student.reload()
            student.locator('.mx-nav [data-view="path"]').click()
            student.locator('.mx-star[data-id="t_ext"]').click()
            expect(student.locator('.mx-sheet [data-skill-res]')).to_be_hidden()
        finally:
            browser.close()
