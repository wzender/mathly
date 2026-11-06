"""Real PostgreSQL transactions and a local private-blob stand-in for tests."""
import json
import uuid
from pathlib import Path

import pytest

from app.answer_scans import AnswerScans, ScanError

OWNER = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'

BOOTSTRAP = '''
create schema auth;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as
 $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
grant usage on schema public,auth to anon,authenticated,service_role;
create schema storage;
create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text,name text unique,created_at timestamptz default now());
alter table storage.objects enable row level security;
grant usage on schema storage to anon,authenticated,service_role;
grant all on storage.objects to anon,authenticated,service_role;
create policy preexisting_permissive on storage.objects for all using(true) with check(true);
create table public.classes(id int primary key,name text);
insert into classes values(1,'existing math class');
'''


class ScanAuth:
    url = 'https://test.invalid'
    key = 'public-test'
    secret = 'server-test'
    # OWNER is a teacher, so these tests check answers straight with the AI; the students' queue is in test_ai_queue
    teachers = frozenset({OWNER + '@test.invalid'})
    developers = frozenset()

    def _admin(self, path, *args, **kwargs):
        from app.auth import AuthUnavailable
        raise AuthUnavailable('supabase answered 404: no tables here but the answer RPCs')

    def user(self, token):
        if token not in (OWNER, OTHER):
            return None
        return {'id': token, 'email': token + '@test.invalid'}

    def classes(self):
        return []

    def user_email(self, user_id):
        return user_id + '@test.invalid'

    def access_for(self, _id, **kwargs):
        return None


class DatabaseAnswers(AnswerScans):
    def __init__(self, uri, files):
        super().__init__(ScanAuth(), enabled=True)
        self.uri, self.files = uri, files
        self.fail_put = self.fail_finalize = False

    def connect(self):
        import psycopg
        return psycopg.connect(self.uri, autocommit=True)

    def action(self, user_id, action, **data):
        return self.rpc('math_answer_action', user_id, action, data)

    def grade(self, user_id, action, **data):
        return self.rpc('math_grade_action', user_id, action, data)

    def quiz(self, user_id, action, **data):
        return self.rpc('math_quiz_action', user_id, action, data)

    def review(self, user_id, action, **data):
        return self.rpc('math_review_action', user_id, action, data)

    def rpc(self, name, user_id, action, data):
        import psycopg
        if self.fail_finalize and action == 'finalize':
            raise ScanError(503, 'answer_storage_unavailable')
        with self.connect() as c:
            c.execute('set role service_role')
            try:
                return c.execute(f'select public.{name}(%s,%s,%s::jsonb)',
                                 (user_id, action, json.dumps(data))).fetchone()[0]
            except psycopg.errors.NoDataFound as exc:
                raise ScanError(404, 'not_found') from exc
            except psycopg.errors.RaiseException as exc:
                message = str(exc).splitlines()[0]
                raise ScanError(429 if message in ('grading_limit', 'review_limit') else 409, message) from exc

    def put(self, key, data):
        if self.fail_put:
            raise ScanError(503, 'answer_storage_unavailable')
        p = self.files / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        with self.connect() as c:
            c.execute("insert into storage.objects(bucket_id,name) values('mathly-answers',%s)", (key,))

    def read(self, key):
        return (self.files / key).read_bytes()

    def delete(self, key):
        (self.files / key).unlink(missing_ok=True)
        with self.connect() as c:
            c.execute('delete from storage.objects where name=%s', (key,))


@pytest.fixture(scope='session')
def postgres_server(tmp_path_factory):
    pgserver = pytest.importorskip('pgserver')
    psycopg = pytest.importorskip('psycopg')
    server = pgserver.get_server(tmp_path_factory.mktemp('postgres') / 'data', cleanup_mode='delete')
    with psycopg.connect(server.get_uri(), autocommit=True) as c:
        c.execute('create role anon; create role authenticated; create role service_role bypassrls;')
    yield server


@pytest.fixture
def answer_store(postgres_server, tmp_path):
    import psycopg
    database = 'scan_' + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute('create database ' + database)
    uri = postgres_server.get_uri(database=database)
    store = DatabaseAnswers(uri, tmp_path / 'images')
    with store.connect() as c:
        c.execute(BOOTSTRAP)
        c.execute(Path('supabase/migrations/20261031133254_math_answer_scans.sql').read_text())
        for migration in sorted(Path('supabase/migrations').glob('*_math_answer_*.sql')):
            if migration.name.endswith('_math_answer_scans.sql'):
                continue
            c.execute(migration.read_text())
        for name in ('quiz_sittings', 'teacher_reviews', 'quiz_modes'):   # in this order: each rewrites a function of the one before
            for migration in sorted(Path('supabase/migrations').glob(f'*_math_{name}.sql')):
                c.execute(migration.read_text())
        c.execute('insert into auth.users values(%s),(%s)', (OWNER, OTHER))
    yield store
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute('drop database ' + database + ' with (force)')
