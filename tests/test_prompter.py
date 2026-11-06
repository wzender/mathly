import asyncio
import urllib.parse
import uuid

import httpx
import pytest

from app.auth import AuthUnavailable
from app.main import create_app
from scan_support import OTHER, OWNER, ScanAuth, postgres_server  # noqa: F401  (a fixture)

DEV = '33333333-3333-4333-8333-333333333333'


class PrompterAuth(ScanAuth):
    """OWNER and DEV are developers, OTHER is a student; an in-memory math_prompter_texts behind the PostgREST calls."""
    developers = frozenset({OWNER + '@test.invalid', DEV + '@test.invalid'})

    def __init__(self):
        self.rows: list[dict] = []
        self.missing = False

    def user(self, token):
        return {'id': token, 'email': token + '@test.invalid'} if token in (OWNER, OTHER, DEV) else None

    def _admin(self, path, method='GET', body=None, prefer=''):
        if self.missing:
            raise AuthUnavailable('supabase answered 404: relation does not exist')
        table, _, query = path.partition('?')
        assert table == '/rest/v1/math_prompter_texts'
        q = dict(urllib.parse.parse_qsl(query))
        match = [r for r in self.rows if all(r[k] == q[k].removeprefix('eq.') for k in ('id', 'user_id') if k in q)]
        if method == 'POST':
            row = {**body, 'id': str(uuid.uuid4())}
            self.rows.append(row)
            return [row]
        if method == 'PATCH':
            for r in match:
                r.update(body)
            return match
        if method == 'DELETE':
            self.rows = [r for r in self.rows if r not in match]
            return None
        return sorted(match, key=lambda r: r['updated_at'], reverse=True)


def call(app, user, method, url, **kw):
    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                     headers={'Authorization': f'Bearer {user}'}) as c:
            return await c.request(method, url, **kw)
    return asyncio.run(go())


@pytest.fixture
def app():
    a = create_app()
    a.state.auth = PrompterAuth()
    return a


def test_developer_saves_lists_updates_and_deletes(app):
    r = call(app, OWNER, 'POST', '/api/prompter/texts', json={'title': '', 'body': '  שלום לכולם\nשורה שנייה'})
    assert r.status_code == 200
    first = r.json()['text']
    assert first['title'] == 'שלום לכולם'                       # no title: the first line
    second = call(app, OWNER, 'POST', '/api/prompter/texts', json={'title': 'פתיחה', 'body': 'טקסט'}).json()['text']
    texts = call(app, OWNER, 'GET', '/api/prompter/texts').json()['texts']
    assert [t['id'] for t in texts] == [second['id'], first['id']]   # newest first
    r = call(app, OWNER, 'PUT', f"/api/prompter/texts/{first['id']}", json={'title': 'חדש', 'body': 'גוף חדש'})
    assert r.json()['text']['title'] == 'חדש' and r.json()['text']['body'] == 'גוף חדש'
    assert call(app, OWNER, 'DELETE', f"/api/prompter/texts/{second['id']}").status_code == 200
    assert [t['title'] for t in call(app, OWNER, 'GET', '/api/prompter/texts').json()['texts']] == ['חדש']


def test_each_developer_sees_only_their_own(app):
    mine = call(app, OWNER, 'POST', '/api/prompter/texts', json={'title': 'שלי', 'body': 'x'}).json()['text']
    assert call(app, DEV, 'GET', '/api/prompter/texts').json()['texts'] == []
    assert call(app, DEV, 'PUT', f"/api/prompter/texts/{mine['id']}", json={'title': 'a', 'body': 'b'}).status_code == 404
    call(app, DEV, 'DELETE', f"/api/prompter/texts/{mine['id']}")
    assert len(call(app, OWNER, 'GET', '/api/prompter/texts').json()['texts']) == 1


def test_students_and_bad_input_are_refused(app):
    assert call(app, OTHER, 'GET', '/api/prompter/texts').status_code == 403
    assert call(app, OTHER, 'POST', '/api/prompter/texts', json={'title': 'a', 'body': 'b'}).status_code == 403
    assert call(app, 'nobody', 'GET', '/api/prompter/texts').status_code == 401
    assert call(app, OWNER, 'POST', '/api/prompter/texts', json={'title': 'a', 'body': '   '}).status_code == 400
    assert call(app, OWNER, 'POST', '/api/prompter/texts', json={'body': 'x' * 100_001}).status_code == 413
    assert call(app, OWNER, 'PUT', '/api/prompter/texts/not-an-id', json={'body': 'x'}).status_code == 404


def test_long_title_is_cut_and_missing_table_is_503(app):
    r = call(app, OWNER, 'POST', '/api/prompter/texts', json={'title': 'א' * 300, 'body': 'x'})
    assert len(r.json()['text']['title']) == 120
    app.state.auth.missing = True
    assert call(app, OWNER, 'GET', '/api/prompter/texts').status_code == 503


def test_migration_on_real_postgres(postgres_server):  # noqa: F811
    """The table exists, keeps its limits, and only the server's key may use it."""
    psycopg = pytest.importorskip("psycopg")
    from pathlib import Path
    from scan_support import BOOTSTRAP
    database = "prm_" + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute("create database " + database)
    uri = postgres_server.get_uri(database=database)
    try:
        with psycopg.connect(uri, autocommit=True) as c:
            c.execute(BOOTSTRAP)
            c.execute(Path("supabase/migrations/20261106130000_math_prompter_texts.sql").read_text())
            c.execute("insert into auth.users values(%s)", (OWNER,))
            c.execute("set role service_role")
            c.execute("insert into math_prompter_texts(user_id,title,body) values(%s,'a','b')", (OWNER,))
            with pytest.raises(psycopg.errors.CheckViolation):
                c.execute("insert into math_prompter_texts(user_id,title,body) values(%s,'','b')", (OWNER,))
            c.execute("reset role")
            c.execute("set role authenticated")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute("select * from math_prompter_texts")
            c.execute("reset role")
            c.execute("delete from auth.users")                       # an account's texts go with it
            assert c.execute("select count(*) from math_prompter_texts").fetchone()[0] == 0
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute("drop database " + database + " with (force)")
