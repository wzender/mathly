"""The teacher's AI queue: a student's request waits for the class teacher, who sends it to the AI or declines it."""
import asyncio
import base64
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.ai_queue import AiQueue, may_send
from app.answer_grading import validate_assessment
from app.answer_scans import ScanError
from app.main import create_app
from app.teacher_ai import TeacherQuota
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server
from test_answer_grading import assessment
from test_answer_scans import begin, finish, png, request

STRANGER = '33333333-3333-4333-8333-333333333333'
mail = lambda uid: uid + '@test.invalid'


@pytest.fixture(autouse=True)
def grading_on(monkeypatch):
    monkeypatch.setenv('MATHLY_OPEN_ENDED_LOCKED', '0')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')


class ClassAuth(ScanAuth):
    """OWNER is a student whose class teacher is OTHER; STRANGER teaches another class."""
    teachers = frozenset()

    def user(self, token):
        return {'id': token, 'email': mail(token)} if token in (OWNER, OTHER, STRANGER) else None

    def classes(self, fresh=False):
        return [{'id': 1, 'name': 'ט1', 'emails': [mail(OWNER), mail(OTHER)], 'teachers': [mail(OTHER)]},
                {'id': 2, 'name': 'ט2', 'emails': [mail(STRANGER), 'x@test.invalid'], 'teachers': [mail(STRANGER)]}]


class MemoryQueue(AiQueue):
    """AiQueue's behaviour over a list, in place of the Supabase table."""
    configured = True

    def __init__(self):
        self.rows = []

    def _new(self, row):
        out = {'id': str(uuid.uuid4()), 'created_at': datetime.now(timezone.utc).isoformat(), 'state': 'pending',
               'attempt_id': None, 'label': '', 'question': '', 'image': None, 'result': None, 'note': '',
               'error': '', 'reviewed_by': '', 'sent_at': None, 'finished_at': None, **row}
        self.rows.append(out)
        return out

    def _public(self, row, image=False):
        return {k: v for k, v in row.items() if image or k != 'image'} if row else None

    def _find(self, rid):
        return next((r for r in self.rows if r['id'] == rid), None)

    def add(self, row):
        if row.get('attempt_id') and any(r['attempt_id'] == row['attempt_id'] and r['state'] in ('pending', 'sending')
                                         for r in self.rows):
            return self.for_attempt(row['user_id'], row['attempt_id'])
        return self._public(self._new(row))

    def for_attempt(self, user_id, attempt_id):
        rows = [r for r in self.rows if r['user_id'] == user_id and r['attempt_id'] == attempt_id]
        return self._public(rows[-1]) if rows else None

    def open_count(self, user_id):
        return sum(r['user_id'] == user_id and r['state'] in ('pending', 'sending') for r in self.rows)

    def mine(self, user_id, limit=20):
        return [self._public(r) for r in reversed(self.rows) if r['user_id'] == user_id and r['kind'] == 'photo']

    def cancel(self, user_id, rid):
        r = self._find(rid)
        if not r or r['user_id'] != user_id or r['state'] != 'pending':
            return None
        r.update(state='cancelled', image=None)
        return self._public(r)

    def reopen(self, rid):
        r = self._find(rid)
        if not r or r['state'] not in ('failed', 'declined'):
            raise ScanError(409, 'request_taken')
        r.update(state='pending', error='', note='')
        return self._public(r)

    def listing(self, emails, limit=100):
        return [self._public(r) for r in reversed(self.rows) if emails is None or r['email'] in emails]

    def get(self, rid, image=False):
        return self._public(self._find(rid), image)

    def claim(self, rid, reviewer):
        r = self._find(rid)
        if not r or r['state'] not in ('pending', 'failed'):
            raise ScanError(409, 'request_taken')
        r.update(state='sending', reviewed_by=reviewer, error='')
        return self._public(r, image=True)

    def finish(self, rid, state, **fields):
        r = self._find(rid)
        r.update(state=state, **fields)
        return self._public(r)

    def decline(self, rid, reviewer, note):
        r = self._find(rid)
        if not r or r['state'] not in ('pending', 'failed'):
            raise ScanError(409, 'request_taken')
        r.update(state='declined', image=None, note=note, reviewed_by=reviewer)
        return self._public(r)


class Grader:
    def __init__(self):
        self.calls = []

    def grade(self, image, snapshot):
        self.calls.append((image, snapshot))
        return validate_assessment(assessment())


class Solver:
    def __init__(self):
        self.calls = []

    def solve(self, image, media_type):
        self.calls.append((image, media_type))
        return {"readable": True, "problem": "$x² = 9$", "steps": [{"hint": "h", "work": "w"}],
                "answer": "$x = ±3$", "skill": "", "note": "", "usage": None}


def make_app(store=None):
    app = create_app(auth=ClassAuth())
    if store is not None:
        app.state.answers = store
    app.state.ai_queue, app.state.answer_grader = MemoryQueue(), Grader()
    app.state.photo, app.state.photo_key = Solver(), 'test-key'
    return app


def as_user(app, uid):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                             headers={'Authorization': f'Bearer {uid}'})


def test_who_sends_to_the_ai_itself():
    assert may_send(None)   # sign-in off
    assert not may_send({'roles': ['student'], 'permissions': ['path.use'], 'email': 's@x', 'classes': []})
    assert may_send({'roles': ['teacher'], 'permissions': [], 'email': 't@x', 'classes': []})
    assert may_send({'roles': ['developer'], 'permissions': ['*'], 'email': 'd@x', 'classes': []})
    assert may_send({'roles': ['student'], 'permissions': [], 'email': 't@x',
                     'classes': [{'teachers': ['t@x'], 'emails': ['t@x']}]})


def test_a_students_answer_waits_for_the_teacher_who_sends_it(answer_store):
    store = answer_store
    upload = begin(store, request(store))
    sid, lid, aid = upload['scan']['id'], upload['scan']['lease_id'], upload['attempt']['id']
    app = make_app(store)
    grader, queue = app.state.answer_grader, app.state.ai_queue

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher, as_user(app, STRANGER) as other:
            me = (await student.get('/api/me')).json()
            assert me['ai_direct'] is False and me['ai_review'] is False
            assert (await teacher.get('/api/me')).json()['ai_review'] is True
            # the upload only keeps the answer: it reaches neither the teacher nor the AI
            up = await student.post(f'/api/math/answer-scans/{sid}/uploads/{lid}',
                                    files={'photo': ('a.png', png(), 'image/png')})
            assert up.status_code == 200 and not grader.calls
            kept = (await student.get(f'/api/math/answer-attempts/{aid}')).json()
            assert kept['grading'] is None and kept['ai_request'] is None and not queue.rows
            assert (await teacher.get('/api/ai-queue')).json()['requests'] == []
            # the student's click sends it to the teacher, never to the AI
            got = (await student.post(f'/api/math/answer-attempts/{aid}/grade')).json()
            assert got['grading'] is None and got['ai_request']['state'] == 'pending' and not grader.calls
            assert 'email' not in got['ai_request']
            # asking again does not make a second request, and does not call the AI
            again = (await student.post(f'/api/math/answer-attempts/{aid}/grade')).json()
            assert again['ai_request']['id'] == got['ai_request']['id'] and len(queue.rows) == 1 and not grader.calls
            # only the class's teacher reviews it
            assert (await student.get('/api/ai-queue')).status_code == 403
            assert (await other.get('/api/ai-queue')).json()['requests'] == []
            rid = got['ai_request']['id']
            assert (await other.post(f'/api/ai-queue/{rid}/send')).status_code == 404
            listed = (await teacher.get('/api/ai-queue')).json()['requests']
            assert [r['id'] for r in listed] == [rid] and listed[0]['email'] == mail(OWNER)
            image = await teacher.get(f'/api/ai-queue/{rid}/image')
            assert image.status_code == 200 and image.headers['content-type'] == 'image/jpeg'
            sent = (await teacher.post(f'/api/ai-queue/{rid}/send')).json()
            assert sent['state'] == 'done' and sent['result']['verdict'] == 'correct' and len(grader.calls) == 1
            assert (await teacher.post(f'/api/ai-queue/{rid}/send')).status_code == 409   # sent once
            done = (await student.get(f'/api/math/answer-attempts/{aid}')).json()
            assert done['grading']['state'] == 'completed' and done['grading']['result']['score'] == 100
    asyncio.run(check())


def test_a_declined_answer_can_be_asked_again(answer_store):
    store = answer_store
    aid = finish(store, begin(store, request(store)))['attempt']['id']
    app = make_app(store)

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            rid = (await student.post(f'/api/math/answer-attempts/{aid}/grade',
                                      json={'automatic': True})).json()['ai_request']['id']
            declined = (await teacher.post(f'/api/ai-queue/{rid}/decline', json={'note': 'צלמו  שוב'})).json()
            assert declined['state'] == 'declined' and declined['note'] == 'צלמו שוב'
            seen = (await student.get(f'/api/math/answer-attempts/{aid}')).json()['ai_request']
            assert seen['state'] == 'declined' and seen['note'] == 'צלמו שוב'
            # the automatic check does not ask again; the student's click does
            auto = (await student.post(f'/api/math/answer-attempts/{aid}/grade', json={'automatic': True})).json()
            assert auto['ai_request']['state'] == 'declined'
            asked = (await student.post(f'/api/math/answer-attempts/{aid}/grade')).json()
            assert asked['ai_request']['id'] == rid and asked['ai_request']['state'] == 'pending'
            assert not app.state.answer_grader.calls
    asyncio.run(check())


def test_a_teachers_own_answer_goes_straight_to_the_ai(answer_store):
    store = answer_store
    aid = finish(store, begin(store, request(store)))['attempt']['id']
    app = make_app(store)
    app.state.auth.teachers = frozenset({mail(OWNER)})   # OWNER has the teacher role now

    async def check():
        async with as_user(app, OWNER) as me:
            result = (await me.post(f'/api/math/answer-attempts/{aid}/grade')).json()
            assert result['grading']['state'] == 'completed' and not app.state.ai_queue.rows
    asyncio.run(check())


def test_a_students_photo_waits_for_the_teacher():
    app = make_app()
    solver, queue = app.state.photo, app.state.ai_queue

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            sent = await student.post('/api/math/photo', files={'photo': ('p.png', png(), 'image/png')})
            assert sent.status_code == 200 and sent.json()['queued'] is True and not solver.calls
            rid = sent.json()['request']['id']
            assert base64.b64decode(queue.rows[0]['image'])[:2] == b'\xff\xd8'   # kept as a clean JPEG
            assert (await student.post('/api/math/photo', files={'photo': ('p.jpg', b'nope', 'image/jpeg')})).status_code == 415
            mine = (await student.get('/api/math/ai-requests')).json()
            assert mine['direct'] is False and mine['requests'][0]['state'] == 'pending'
            assert (await teacher.get(f'/api/ai-queue/{rid}/image')).status_code == 200
            done = (await teacher.post(f'/api/ai-queue/{rid}/send')).json()
            assert done['state'] == 'done' and len(solver.calls) == 1 and solver.calls[0][1] == 'image/jpeg'
            assert queue.rows[0]['image'] is None   # the photo is not kept once it is answered
            mine = (await student.get('/api/math/ai-requests')).json()['requests'][0]
            assert mine['state'] == 'done' and mine['result']['answer'] == '$x = ±3$' and 'usage' not in mine['result']
            # the teacher's own photo is solved at once
            own = (await teacher.post('/api/math/photo', files={'photo': ('p.png', png(), 'image/png')})).json()
            assert own['answer'] == '$x = ±3$' and len(queue.rows) == 1
    asyncio.run(check())


def test_a_student_can_cancel_and_has_a_limit_of_open_requests():
    app = make_app()

    async def check():
        async with as_user(app, OWNER) as student:
            ids = []
            for _ in range(5):
                ids.append((await student.post('/api/math/photo', files={'photo': ('p.png', png(), 'image/png')})).json()['request']['id'])
            assert (await student.post('/api/math/photo', files={'photo': ('p.png', png(), 'image/png')})).status_code == 429
            assert (await student.post(f'/api/math/ai-requests/{ids[0]}/cancel')).json()['state'] == 'cancelled'
            assert (await student.post(f'/api/math/ai-requests/{ids[0]}/cancel')).status_code == 409
            assert (await student.post('/api/math/photo', files={'photo': ('p.png', png(), 'image/png')})).status_code == 200
    asyncio.run(check())


def test_the_migration_keeps_one_open_request_per_answer(postgres_server):
    import psycopg
    database = 'queue_' + uuid.uuid4().hex
    with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
        c.execute('create database ' + database)
    try:
        with psycopg.connect(postgres_server.get_uri(database=database), autocommit=True) as c:
            c.execute('create schema auth; create table auth.users(id uuid primary key);')
            c.execute(Path('supabase/migrations/20261104090000_math_ai_requests.sql').read_text())
            c.execute('insert into auth.users values(%s)', (OWNER,))
            attempt = str(uuid.uuid4())
            add = "insert into public.math_ai_requests(user_id,email,kind,attempt_id) values(%s,'s@x','grading',%s)"
            c.execute(add, (OWNER, attempt))
            with pytest.raises(psycopg.errors.UniqueViolation):
                c.execute(add, (OWNER, attempt))
            c.execute("update public.math_ai_requests set state='done'")
            c.execute(add, (OWNER, attempt))   # a new request once the first is handled
            with pytest.raises(psycopg.errors.CheckViolation):   # a photo has no answer; an answer check needs one
                c.execute("insert into public.math_ai_requests(user_id,email,kind,attempt_id) values(%s,'s@x','photo',%s)",
                          (OWNER, attempt))
            c.execute("set role anon")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute('select * from public.math_ai_requests')
    finally:
        with psycopg.connect(postgres_server.get_uri(), autocommit=True) as c:
            c.execute('drop database ' + database + ' with (force)')


def test_a_failed_send_keeps_why_it_failed(answer_store):
    from app.math_photo import PhotoUnavailable
    store = answer_store
    aid = finish(store, begin(store, request(store)))['attempt']['id']
    app = make_app(store)

    class Refused:
        def grade(self, image, snapshot):
            raise PhotoUnavailable('הבדיקה אינה זמינה כרגע.', 'api_key_invalid', 'AuthenticationError 401: invalid x-api-key')
    app.state.answer_grader = Refused()

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            rid = (await student.post(f'/api/math/answer-attempts/{aid}/grade')).json()['ai_request']['id']
            failed = (await teacher.post(f'/api/ai-queue/{rid}/send')).json()
            assert failed['state'] == 'failed'
            assert failed['error'] == 'grading_failed|api_key_invalid|AuthenticationError 401: invalid x-api-key'
            assert 'error' not in (await student.get(f'/api/math/answer-attempts/{aid}')).json()['ai_request']
    asyncio.run(check())


def test_a_teachers_own_failed_check_says_why(answer_store, monkeypatch):
    store = answer_store
    aid = finish(store, begin(store, request(store)))['attempt']['id']
    app = make_app(store)
    app.state.auth.teachers = frozenset({mail(OWNER)})
    monkeypatch.delenv('ANTHROPIC_API_KEY')

    async def check():
        async with as_user(app, OWNER) as me:
            body = (await me.post(f'/api/math/answer-attempts/{aid}/grade')).json()
            assert body == {'detail': 'grading_unavailable', 'reason': 'missing_key',
                            'error_detail': 'ANTHROPIC_API_KEY is not set'}
    asyncio.run(check())


@pytest.mark.parametrize('status,message,reason', [
    (401, 'invalid x-api-key', 'api_key_invalid'), (403, 'no access', 'permission'),
    (404, 'model: claude-x', 'model_not_found'), (429, 'slow down', 'rate_limited'),
    (400, 'Your credit balance is too low to access the Anthropic API.', 'no_credit'),
    (529, 'Overloaded', 'overloaded'), (400, 'bad image', 'bad_request')])
def test_api_errors_are_named(status, message, reason):
    import anthropic
    from app.math_photo import failure_reason
    response = httpx.Response(status, request=httpx.Request('POST', 'https://api.anthropic.com/v1/messages'))
    cls = {401: anthropic.AuthenticationError, 403: anthropic.PermissionDeniedError, 404: anthropic.NotFoundError,
           429: anthropic.RateLimitError, 400: anthropic.BadRequestError}.get(status, anthropic.InternalServerError)
    exc = cls(message, response=response, body=None)
    got, detail = failure_reason(exc)
    assert got == reason and str(status) in detail and message[:20] in detail
    assert failure_reason(anthropic.APIConnectionError(request=response.request))[0] == 'no_connection'


class ReportAuth(ClassAuth):
    """ClassAuth that can also answer the class report's two lookups: user ids and (empty) saved progress."""
    def user_accounts(self, emails):
        return {mail(uid): {'id': uid, 'name': ''} for uid in (OWNER, OTHER) if mail(uid) in emails}

    def user_email(self, user_id):
        return mail(user_id)

    def _admin(self, path, *args, **kwargs):
        if path.startswith('/rest/v1/math_progress'):
            return []
        return super()._admin(path, *args, **kwargs)


async def hand_in_quiz(student, unit):
    """The student photographs the four answers of a unit quiz, hands it in and asks each answer to be checked (as the
    page does). Returns the attempt ids, the queue request ids and the sitting."""
    from app.math_skills import question_version, quiz_snapshot
    attempts, requests = [], []
    for index in range(4):
        version = question_version(quiz_snapshot(unit, index))
        made = (await student.post('/api/math/quiz-attempts',
                                   json={'unit': unit['id'], 'index': index, 'question_version': version, 'new': True})).json()
        aid = made['attempt']['id']
        scan = (await student.post(f'/api/math/answer-attempts/{aid}/scans', json={'renew': True})).json()['scan']
        await student.post(f"/api/math/answer-scans/{scan['id']}/confirm")
        lease = (await student.post(f"/api/math/answer-scans/{scan['id']}/uploads", json={'key': str(uuid.uuid4())})).json()
        up = await student.post(f"/api/math/answer-scans/{scan['id']}/uploads/{lease['lease_id']}",
                                files={'photo': ('a.png', png(), 'image/png')})
        assert up.status_code == 200
        attempts.append(aid)
    handed = (await student.post('/api/math/quiz-sittings', json={'unit_id': unit['id'], 'attempts': attempts,
                                                                'client_key': str(uuid.uuid4())})).json()
    for aid in attempts:
        asked = (await student.post(f'/api/math/answer-attempts/{aid}/grade', json={})).json()
        requests.append(asked['ai_request']['id'])
    return attempts, requests, handed


def test_a_quiz_checked_through_the_teachers_queue_has_one_grade_for_student_and_teacher(answer_store):
    """The student hands in a unit quiz; each answer waits in the teacher's queue. The sitting has no grade until the
    teacher has sent them all, and then the student's screen and the teacher's class report show the same grade."""
    from app.math_skills import algebra9

    store = answer_store
    app = create_app(auth=ReportAuth())
    app.state.answers, app.state.ai_queue = store, MemoryQueue()
    app.state.teacher_ai = TeacherQuota(daily=100)   # a whole quiz's answers: more than the teacher's 3 a day
    scores = {0: 100, 1: 60, 2: 100, 3: 40}

    class ByQuestion:
        def grade(self, image, snapshot):
            return validate_assessment(assessment(score=scores[int(snapshot['name'][-1]) - 1]))
    app.state.answer_grader = ByQuestion()
    unit = next(u for u in algebra9()['units'] if u['id'] == 't')

    async def check():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            attempts, requests, handed = await hand_in_quiz(student, unit)
            assert handed['grade'] is None and handed['open'] == 4          # every answer waits for the teacher

            def seen_by_teacher():
                return teacher.get('/api/classes/1/report')

            for rid in requests[:3]:
                assert (await teacher.post(f'/api/ai-queue/{rid}/send')).status_code == 200
            mine = (await student.get('/api/math/quiz-sittings', params={'unit_id': 't'})).json()['sittings'][0]
            report = (await seen_by_teacher()).json()['students'][0]['quiz_sittings'][0]
            assert mine['grade'] is None and report['grade'] is None and mine['open'] == report['open'] == 1
            assert (await teacher.post(f'/api/ai-queue/{requests[3]}/send')).status_code == 200
            mine = (await student.get('/api/math/quiz-sittings', params={'unit_id': 't'})).json()['sittings'][0]
            report = (await seen_by_teacher()).json()['students'][0]['quiz_sittings'][0]
            assert mine['grade'] == report['grade'] == 25 + 15 + 25 + 10 and mine['id'] == report['id'] == handed['id']
    asyncio.run(check())


def test_a_student_disputes_a_check_and_the_teachers_correction_reaches_both_screens(answer_store):
    """The whole path: the student hands in a quiz, the teacher sends every answer to the AI, the student asks the
    teacher to look again at one, the teacher corrects it with a comment, and the new grade, the comment and the closed
    request show on the student's screen and in the teacher's class report."""
    from app.math_skills import algebra9

    app = create_app(auth=ReportAuth())
    app.state.answers, app.state.ai_queue = answer_store, MemoryQueue()
    app.state.teacher_ai = TeacherQuota(daily=100)   # a whole quiz's answers: more than the teacher's 3 a day
    scores = {0: 100, 1: 60, 2: 100, 3: 40}

    class ByQuestion:
        def grade(self, image, snapshot):
            return validate_assessment(assessment(score=scores[int(snapshot['name'][-1]) - 1]))
    app.state.answer_grader = ByQuestion()
    unit = next(u for u in algebra9()['units'] if u['id'] == 't')

    async def run():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            attempts, requests, handed = await hand_in_quiz(student, unit)
            for rid in requests:
                assert (await teacher.post(f'/api/ai-queue/{rid}/send')).status_code == 200
            sittings = lambda: student.get('/api/math/quiz-sittings', params={'unit_id': 't'})
            card = lambda: teacher.get('/api/classes/1/report')
            assert (await sittings()).json()['sittings'][0]['grade'] == 25 + 15 + 25 + 10      # the AI's: 75
            # the student disagrees with the second check
            asked = await student.post(f'/api/math/answer-attempts/{attempts[1]}/review-request', json={'message': 'כתבתי x=4'})
            assert asked.status_code == 200
            waiting = (await teacher.get('/api/teacher/review-requests')).json()['requests']
            assert [(x['attempt_id'], x['student'], x['message']) for x in waiting] == [(attempts[1], mail(OWNER), 'כתבתי x=4')]
            assert (await card()).json()['students'][0]['review_requests'][0]['attempt_id'] == attempts[1]
            opened = (await teacher.get(f'/api/teacher/answers/{attempts[1]}')).json()
            assert opened['grading']['result']['score'] == 60 and opened['request']['state'] == 'open'
            assert (await teacher.get(f'/api/teacher/answers/{attempts[1]}/image')).status_code == 200
            # the teacher agrees with the student
            saved = await teacher.put(f'/api/teacher/answers/{attempts[1]}/review', json={'score': 100, 'comment': 'צדקתם, הפתרון נכון'})
            assert saved.status_code == 200 and saved.json()['request']['state'] == 'closed'
            # the student's screen: the new grade, the teacher's words, the AI's check unchanged, the request closed
            mine = (await sittings()).json()['sittings'][0]
            assert mine['grade'] == 25 + 25 + 25 + 10 and mine['questions'][1]['state'] == 'teacher'
            assert [c['comment'] for c in (await student.get('/api/math/teacher-comments')).json()['comments']] == ['צדקתם, הפתרון נכון']
            answer = (await student.get(f'/api/math/answer-attempts/{attempts[1]}')).json()
            assert answer['teacher_review']['score'] == 100 and answer['grading']['result']['score'] == 60
            assert answer['review_request']['state'] == 'closed' and answer['effective_score'] == 100
            assert (await student.get('/api/math/teacher-comments')).json() == {'comments': []}
            # the teacher's report: the same grade, and nobody waiting
            report = (await card()).json()['students'][0]
            assert report['quiz_sittings'][0]['grade'] == mine['grade'] == 85 and report['quiz_sittings'][0]['id'] == handed['id']
            assert report['review_requests'] == []
            assert (await teacher.get('/api/teacher/review-requests')).json() == {'requests': []}
    asyncio.run(run())


def test_handing_a_quiz_in_queues_every_photographed_answer_for_the_teacher_without_the_page_asking(answer_store):
    """A student's answers all reach their teacher at hand-in, even if the page never asks for the checks one by one."""
    from app.math_skills import algebra9, question_version, quiz_snapshot
    from test_unit_quiz import quiz_answer

    app = make_app(answer_store)
    app.state.auth = ReportAuth()
    unit = next(u for u in algebra9()['units'] if u['id'] == 't')
    ids = [quiz_answer(answer_store, i, photo=i != 2) for i in range(4)]   # the third question has no photo
    key = str(uuid.uuid4())

    async def run():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            r = await student.post('/api/math/quiz-sittings', json={'unit_id': 't', 'attempts': ids, 'client_key': key})
            assert r.status_code == 200
            rows = (await teacher.get('/api/ai-queue')).json()['requests']
            assert sorted(x['label'][-1] for x in rows) == ['1', '2', '4'] and {x['state'] for x in rows} == {'pending'}
            assert {x['attempt_id'] for x in rows} == {ids[0], ids[1], ids[3]} and all(x['kind'] == 'grading' for x in rows)
            # handing the same quiz in again changes nothing, and the page's own checks find the requests waiting
            assert (await student.post('/api/math/quiz-sittings', json={'unit_id': 't', 'attempts': ids, 'client_key': key})).status_code == 200
            assert len((await teacher.get('/api/ai-queue')).json()['requests']) == 3
            asked = (await student.post(f'/api/math/answer-attempts/{ids[0]}/grade', json={})).json()
            assert asked['ai_request']['state'] == 'pending' and len((await teacher.get('/api/ai-queue')).json()['requests']) == 3
            # an answer the teacher declined stays declined when the hand-in is repeated
            declined = rows[0]['id']
            await teacher.post(f'/api/ai-queue/{declined}/decline', json={'note': 'צלמו שוב'})
            await student.post('/api/math/quiz-sittings', json={'unit_id': 't', 'attempts': ids, 'client_key': key})
            states = {x['id']: x['state'] for x in (await teacher.get('/api/ai-queue')).json()['requests']}
            assert states[declined] == 'declined' and len(states) == 3
    asyncio.run(run())
    assert len(app.state.ai_queue.rows) == 3


def test_a_teachers_own_hand_in_does_not_go_through_the_queue(answer_store):
    """Accounts that send straight to the AI keep doing so: the hand-in queues nothing for them."""
    from test_unit_quiz import quiz_answer

    app = make_app(answer_store)
    app.state.auth = ReportAuth()
    app.state.auth.teachers = frozenset({mail(OWNER)})   # OWNER has the teacher role now
    ids = [quiz_answer(answer_store, i) for i in range(4)]

    async def run():
        async with as_user(app, OWNER) as me:
            assert (await me.post('/api/math/quiz-sittings', json={'unit_id': 't', 'attempts': ids, 'client_key': str(uuid.uuid4())})).status_code == 200
    asyncio.run(run())
    assert app.state.ai_queue.rows == []
