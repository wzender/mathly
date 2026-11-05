"""The class teacher's review of an open answer, and the student's request to look again.
Answers are kept in real PostgreSQL (scan_support); the AI check is a stand-in."""
import asyncio
import uuid

import httpx
import psycopg
import pytest

from app.answer_grading import validate_assessment
from app.answer_scans import ScanError, clean_image
from app.main import create_app
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server
from test_answer_grading import assessment
from test_ai_queue import ClassAuth, STRANGER, as_user, mail
from test_answer_scans import png, request


def photographed(store, owner=OWNER, question='geometry'):
    """An attempt of `owner` with a saved photo; returns its id."""
    sid = request(store, owner, question=question)['scan']['id']
    store.action(owner, 'confirm', scan_id=sid)
    scan = store.action(owner, 'begin', scan_id=sid, key=str(uuid.uuid4()))['scan']
    key = f"{owner}/{scan['id']}/{scan['lease_id']}/{uuid.uuid4()}.jpg"
    store.put(key, clean_image(png(), 'image/png'))
    done = store.action(owner, 'finalize', scan_id=scan['id'], lease_id=scan['lease_id'], object_key=key, byte_size=500)
    return done['attempt']['id']


def test_the_reviews_migration_is_additive_and_service_only(answer_store):
    with answer_store.connect() as c:
        assert c.execute("select name from classes").fetchone()[0] == "existing math class"
        for table in ("math_teacher_reviews", "math_review_requests"):
            assert c.execute("select relrowsecurity from pg_class where relname=%s", (table,)).fetchone()[0]
            c.execute("set role authenticated")
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                c.execute(f"select * from {table}")
            c.execute("reset role")
        c.execute("set role anon")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select math_review_action(null,'requests','{}')")


def test_a_review_replaces_the_one_before_and_closes_the_students_request(answer_store):
    store = answer_store
    aid = photographed(store)
    assert store.review(OWNER, 'get', attempt_id=aid) == {'review': None, 'request': None}
    asked = store.review(OWNER, 'request', attempt_id=aid, message='כתבתי x=4')
    assert asked['request']['state'] == 'open' and asked['request']['message'] == 'כתבתי x=4'
    assert store.review(OWNER, 'request', attempt_id=aid)['request']['id'] == asked['request']['id']   # one open request
    with answer_store.connect() as c:   # the database itself keeps a second open request out
        with pytest.raises(psycopg.errors.UniqueViolation):
            c.execute("insert into math_review_requests(user_id, attempt_id) select user_id, attempt_id from math_review_requests")
    first = store.review(OWNER, 'review', attempt_id=aid, reviewer='t@x', score=85, comment='הדרך נכונה')
    assert first['review']['score'] == 85 and first['review']['reviewer_email'] == 't@x'
    assert first['request']['state'] == 'closed'
    second = store.review(OWNER, 'review', attempt_id=aid, reviewer='t@x', score=None, comment='רק הערה')
    assert second['review']['score'] is None and second['review']['comment'] == 'רק הערה'   # replaces, not merges
    assert store.review(OWNER, 'owner', attempt_id=aid) == OWNER
    with answer_store.connect() as c:
        assert c.execute("select count(*) from math_teacher_reviews").fetchone()[0] == 2   # the first is history


def test_only_an_answer_with_a_photo_can_be_reviewed_or_questioned(answer_store):
    store = answer_store
    bare = store.action(OWNER, 'resume', question_id='geometry', question_version='v1',
                        snapshot={'question': 'q', 'type': 'open-ended'})['attempt']['id']
    for action, data in (('review', {'score': 50, 'reviewer': 't@x'}), ('request', {})):
        with pytest.raises(ScanError, match='answer_required'):
            store.review(OWNER, action, attempt_id=bare, **data)
    with pytest.raises(ScanError) as exc:
        store.review(OTHER, 'get', attempt_id=photographed(store))   # another student's answer
    assert exc.value.status == 404


def test_a_review_needs_a_score_or_a_comment_and_a_sane_score(answer_store):
    store = answer_store
    aid = photographed(store)
    with pytest.raises(Exception):
        store.review(OWNER, 'review', attempt_id=aid, reviewer='t@x', score=None, comment='')
    with pytest.raises(Exception):
        store.review(OWNER, 'review', attempt_id=aid, reviewer='t@x', score=120, comment='')
    assert store.review(OWNER, 'get', attempt_id=aid)['review'] is None


def test_a_student_has_at_most_five_open_requests(answer_store):
    store = answer_store
    ids = [photographed(store, question=f'q{i}') for i in range(6)]
    for aid in ids[:5]:
        store.review(OWNER, 'request', attempt_id=aid)
    with pytest.raises(ScanError) as exc:
        store.review(OWNER, 'request', attempt_id=ids[5])
    assert (exc.value.status, exc.value.code) == (429, 'review_limit')
    store.review(OWNER, 'review', attempt_id=ids[0], reviewer='t@x', score=70, comment='')   # one closes: room again
    assert store.review(OWNER, 'request', attempt_id=ids[5])['request']['state'] == 'open'


def test_unseen_reviews_are_listed_until_the_student_opens_the_answer(answer_store):
    store = answer_store
    aid = photographed(store)
    assert store.review(OWNER, 'unseen') == []
    store.review(OWNER, 'review', attempt_id=aid, reviewer='t@x', score=60, comment='נסו שוב')
    unseen = store.review(OWNER, 'unseen')
    assert [(x['attempt_id'], x['score'], x['comment']) for x in unseen] == [(aid, 60, 'נסו שוב')]
    assert store.review(OTHER, 'unseen') == []
    store.review(OWNER, 'seen', attempt_id=aid)
    assert store.review(OWNER, 'unseen') == []
    store.review(OWNER, 'review', attempt_id=aid, reviewer='t@x', score=90, comment='תוקן')   # a newer review: unseen again
    assert len(store.review(OWNER, 'unseen')) == 1


def test_open_requests_are_listed_for_chosen_students(answer_store):
    store = answer_store
    mine, theirs = photographed(store), photographed(store, OTHER)
    store.review(OWNER, 'request', attempt_id=mine, message='א')
    store.review(OTHER, 'request', attempt_id=theirs, message='ב')
    both = store.review(None, 'requests')
    assert {x['attempt_id'] for x in both} == {mine, theirs}
    only = store.review(None, 'requests', users=[OWNER])
    assert [(x['attempt_id'], x['user_id'], x['message']) for x in only] == [(mine, OWNER, 'א')]
    assert store.review(None, 'requests', users=[]) == []


# ---- the teacher's routes. OWNER is a student of class 1, whose teacher is OTHER; STRANGER teaches class 2.
class ReviewAuth(ClassAuth):
    def user_email(self, user_id):
        return mail(user_id)

    def user_accounts(self, emails):
        return {mail(uid): {'id': uid, 'name': ''} for uid in (OWNER, OTHER, STRANGER) if mail(uid) in emails}


def checked(store, aid, score=40, verdict='partial'):
    lease = str(uuid.uuid4())
    store.grade(OWNER, 'start', attempt_id=aid, lease_id=lease)
    store.grade(OWNER, 'complete', attempt_id=aid, lease_id=lease, result={'verdict': verdict, 'score': score})


def review_app(store, manager=False):
    auth = ReviewAuth()
    if manager:
        auth.developers = frozenset({mail(STRANGER)})   # STRANGER is a manager (a developer) here
    app = create_app(auth=auth)
    app.state.answers = store
    return app


def test_the_class_teacher_opens_an_answer_with_its_photo_and_check(answer_store):
    store = answer_store
    aid = photographed(store)
    checked(store, aid, 40)
    app = review_app(store)

    async def run():
        async with as_user(app, OTHER) as teacher:
            r = await teacher.get(f'/api/teacher/answers/{aid}')
            assert r.status_code == 200
            data = r.json()
            assert data['student'] == {'email': mail(OWNER)} and data['grading']['result']['score'] == 40
            assert 'object_key' not in str(data) and data['effective_score'] == 40
            assert data['attempt']['snapshot']['question'] and data['review'] is None and data['request'] is None
            image = await teacher.get(f'/api/teacher/answers/{aid}/image')
            assert image.status_code == 200 and image.headers['content-type'] == 'image/jpeg' and image.content
            assert image.headers['cache-control'] == 'no-store'
    asyncio.run(run())


def test_other_accounts_are_refused_and_get_neither_the_check_nor_the_image(answer_store):
    store = answer_store
    aid = photographed(store)
    checked(store, aid)
    app = review_app(store)

    async def run():
        async with as_user(app, STRANGER) as other, as_user(app, OWNER) as student:
            for client, status in ((other, 403), (student, 403)):   # another class's teacher; the student themself
                for path in (f'/api/teacher/answers/{aid}', f'/api/teacher/answers/{aid}/image'):
                    r = await client.get(path)
                    assert r.status_code == status and r.headers['content-type'].startswith('application/json')
                    assert 'score' not in r.text and 'attachment' not in r.text
            assert (await other.put(f'/api/teacher/answers/{aid}/review', json={'score': 100})).status_code == 403
            assert (await other.get(f'/api/teacher/answers/{uuid.uuid4()}')).status_code == 404
    asyncio.run(run())
    with answer_store.connect() as c:
        assert c.execute('select count(*) from math_teacher_reviews').fetchone()[0] == 0


def test_a_manager_may_open_any_answer(answer_store):
    store = answer_store
    aid = photographed(store)
    app = review_app(store, manager=True)

    async def run():
        async with as_user(app, STRANGER) as manager:
            assert (await manager.get(f'/api/teacher/answers/{aid}')).status_code == 200
            assert (await manager.get(f'/api/teacher/answers/{aid}/image')).status_code == 200
    asyncio.run(run())


def test_the_teacher_corrects_a_score_and_grades_what_the_ai_could_not_read(answer_store):
    store = answer_store
    first, unreadable = photographed(store, question='a'), photographed(store, question='b')
    checked(store, first, 40)
    checked(store, unreadable, None, verdict='unreadable')
    app = review_app(store)

    async def run():
        async with as_user(app, OTHER) as teacher:
            put = lambda aid, **body: teacher.put(f'/api/teacher/answers/{aid}/review', json=body)
            r = await put(first, score=85, comment='הדרך נכונה, טעות חישוב בשורה 3')
            assert r.status_code == 200 and r.json()['review']['score'] == 85
            assert r.json()['review']['reviewer_email'] == mail(OTHER)
            seen = (await teacher.get(f'/api/teacher/answers/{first}')).json()
            assert seen['grading']['result']['score'] == 40 and seen['effective_score'] == 85   # the AI's check is kept
            assert (await put(unreadable, score=70)).status_code == 200
            assert (await teacher.get(f'/api/teacher/answers/{unreadable}')).json()['effective_score'] == 70
            assert (await put(first, comment='רק הערה')).json()['review']['score'] is None   # a newer review replaces
            for bad in ({}, {'comment': '   '}, {'score': 120}, {'score': -1}, {'score': 7.5}, {'score': True},
                        {'score': '80'}, {'comment': 'א' * 1001}, {'comment': 5}):
                assert (await put(first, **bad)).status_code == 400, bad
            assert (await put(first, score=0, comment='')).status_code == 200      # zero is a score
            assert (await put(first, comment='א' * 1000)).status_code == 200
    asyncio.run(run())


def test_requests_to_look_again_are_listed_for_the_class_teacher_until_answered(answer_store):
    store = answer_store
    aid = photographed(store)
    store.review(OWNER, 'request', attempt_id=aid, message='כתבתי x=4')
    app = review_app(store)
    app_manager = review_app(store, manager=True)

    async def run():
        async with as_user(app, OTHER) as teacher, as_user(app, STRANGER) as other:
            listed = (await teacher.get('/api/teacher/review-requests')).json()['requests']
            assert [(x['attempt_id'], x['student'], x['message']) for x in listed] == [(aid, mail(OWNER), 'כתבתי x=4')]
            assert 'user_id' not in listed[0] and listed[0]['question']
            assert (await other.get('/api/teacher/review-requests')).json() == {'requests': []}   # another class's teacher
            async with as_user(app_manager, STRANGER) as manager:
                assert len((await manager.get('/api/teacher/review-requests')).json()['requests']) == 1
            assert (await teacher.put(f'/api/teacher/answers/{aid}/review', json={'comment': 'בדקתי שוב'})).status_code == 200
            assert (await teacher.get('/api/teacher/review-requests')).json() == {'requests': []}
    asyncio.run(run())


# ---- what the student sees and can do
@pytest.fixture(autouse=True)
def open_ended_unlocked(monkeypatch):
    monkeypatch.setenv('MATHLY_OPEN_ENDED_LOCKED', '0')
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')


def test_the_student_sees_the_teachers_review_apart_from_the_ai_check(answer_store):
    store = answer_store
    aid = photographed(store)
    checked(store, aid, 40)
    app = review_app(store)

    async def run():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            got = (await student.get(f'/api/math/answer-attempts/{aid}')).json()
            assert got['teacher_review'] is None and got['review_request'] is None and got['effective_score'] == 40
            assert (await student.get('/api/math/teacher-comments')).json() == {'comments': []}
            await teacher.put(f'/api/teacher/answers/{aid}/review', json={'score': 85, 'comment': 'הדרך נכונה'})
            comments = (await student.get('/api/math/teacher-comments')).json()['comments']
            assert [(x['attempt_id'], x['score'], x['comment']) for x in comments] == [(aid, 85, 'הדרך נכונה')]
            got = await student.get(f'/api/math/answer-attempts/{aid}')
            data = got.json()
            assert data['teacher_review']['score'] == 85 and data['teacher_review']['comment'] == 'הדרך נכונה'
            assert data['grading']['result']['score'] == 40 and data['effective_score'] == 85   # both, labelled apart
            assert mail(OTHER) not in got.text and 'reviewer' not in got.text                   # no teacher email
            assert (await student.get('/api/math/teacher-comments')).json() == {'comments': []}   # opened: seen
            await teacher.put(f'/api/teacher/answers/{aid}/review', json={'comment': 'תוקן'})
            assert len((await student.get('/api/math/teacher-comments')).json()['comments']) == 1   # a newer one
            assert (await student.get('/api/math/answer-attempts/' + aid)).json()['teacher_review']['comment'] == 'תוקן'
    asyncio.run(run())


def test_the_teacher_checking_on_the_students_behalf_does_not_mark_a_review_seen(answer_store):
    store = answer_store
    aid = photographed(store)
    app = review_app(store)

    async def run():
        async with as_user(app, OTHER) as teacher, as_user(app, OWNER) as student:
            await teacher.put(f'/api/teacher/answers/{aid}/review', json={'score': 50})
            await teacher.get(f'/api/teacher/answers/{aid}')
            assert len((await student.get('/api/math/teacher-comments')).json()['comments']) == 1
    asyncio.run(run())


def test_a_student_asks_the_teacher_to_look_again(answer_store):
    store = answer_store
    ids = [photographed(store, question=f'q{i}') for i in range(6)]
    app = review_app(store)

    async def run():
        async with as_user(app, OWNER) as student, as_user(app, OTHER) as teacher:
            ask = lambda aid, **body: student.post(f'/api/math/answer-attempts/{aid}/review-request', json=body)
            r = await ask(ids[0], message='כתבתי x=4, לא x=1')
            assert r.status_code == 200 and r.json()['review_request']['state'] == 'open'
            again = await ask(ids[0], message='שוב')
            assert again.json()['review_request']['id'] == r.json()['review_request']['id']   # one open request
            assert (await student.get(f'/api/math/answer-attempts/{ids[0]}')).json()['review_request']['state'] == 'open'
            assert (await ask(ids[1], message='א' * 301)).status_code == 400
            assert (await ask(ids[1], message=7)).status_code == 400
            for aid in ids[1:5]:
                assert (await ask(aid)).status_code == 200                                      # five open
            assert (await ask(ids[5])).status_code == 429
            await teacher.put(f'/api/teacher/answers/{ids[0]}/review', json={'score': 100})
            closed = (await student.get(f'/api/math/answer-attempts/{ids[0]}')).json()['review_request']
            assert closed['state'] == 'closed'
            assert (await ask(ids[5])).status_code == 200                                       # room again
            other = as_user(app, OTHER)
            async with other as stranger:   # a request is for the student's own answers only
                assert (await stranger.post(f'/api/math/answer-attempts/{ids[0]}/review-request', json={})).status_code == 404
    asyncio.run(run())


def test_a_teacher_score_changes_the_grade_of_a_handed_in_quiz(answer_store):
    from test_unit_quiz import check, quiz_answer
    store = answer_store
    ids = [quiz_answer(store, i) for i in range(4)]
    for aid in ids:
        check(store, aid, 100)
    app = review_app(store)

    async def run():
        async with as_user(app, OWNER) as student:
            made = (await student.post('/api/math/quiz-sittings', json={
                'unit_id': 't', 'attempts': ids, 'client_key': str(uuid.uuid4())})).json()
            assert made['grade'] == 100
            store.review(OWNER, 'review', attempt_id=ids[1], reviewer=mail(OTHER), score=40, comment='')
            mine = (await student.get('/api/math/quiz-sittings', params={'unit_id': 't'})).json()['sittings'][0]
            assert mine['grade'] == 25 + 10 + 25 + 25 and mine['questions'][1]['state'] == 'teacher'
    asyncio.run(run())
