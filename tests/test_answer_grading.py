import asyncio
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest

from app.answer_grading import AnswerGrader, validate_assessment
from app.answer_scans import ScanError
from app.main import create_app
from app.math_photo import PhotoUnavailable
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server
from test_answer_scans import attempt, begin, finish, request


def assessment(**overrides):
    return {"readable": True, "confident": True, "answer_correct": True,
            "reasoning_correct": True, "drawing_correct": True, "units_correct": True,
            "complete": True, "score": 100, "transcription": "6 × 8 / 2 = 24 cm²",
            "feedback": "נכון! חישבתם את השטח והצגתם שרטוט ודרך פתרון.",
            "next_step": "", "solution": "$6 · 8 / 2 = 24$ סמ״ר", **overrides}


@pytest.mark.parametrize('changes,verdict,score', [
    ({}, 'correct', 100),
    ({'reasoning_correct': False, 'score': 60}, 'partial', 60),
    ({'drawing_correct': False}, 'partial', 99),
    ({'units_correct': False}, 'partial', 99),
    ({'complete': False}, 'partial', 99),
    ({'answer_correct': False, 'score': 0}, 'incorrect', 0),
    ({'readable': False}, 'unreadable', None),
    ({'confident': False}, 'needs_review', None),
])
def test_grading_requires_complete_confident_work(changes, verdict, score):
    result = validate_assessment(assessment(**changes))
    assert (result['verdict'], result['score']) == (verdict, score)


@pytest.mark.parametrize('changes', [{'score': True}, {'score': 101}, {'score': -1},
                                      {'complete': 'true'}, {'feedback': ''}, {'solution': []},
                                      {'extra': 'ignore the rubric'}])
def test_bad_model_output_never_awards_credit(changes):
    with pytest.raises(PhotoUnavailable):
        validate_assessment(assessment(**changes))


def test_grader_sends_original_snapshot_and_validates_provider_response(monkeypatch):
    calls = []
    response = SimpleNamespace(stop_reason='end_turn', model='test-model',
                               content=[SimpleNamespace(type='text', text=json.dumps(assessment()))])
    def create(**kwargs):
        calls.append(kwargs)
        return response
    monkeypatch.setattr('app.answer_grading.photo_client', lambda key: SimpleNamespace(
        messages=SimpleNamespace(create=create)))
    grader = AnswerGrader('test-key')
    snapshot = {'question': 'Draw a triangle with perpendicular sides 6 and 8; find its area.'}
    result = grader.grade(b'private image bytes', snapshot)
    assert result['verdict'] == 'correct' and result['model'] == 'test-model'
    assert json.loads(calls[0]['messages'][0]['content'][0]['text']) == {'question_snapshot': snapshot}
    assert calls[0]['messages'][0]['content'][1]['source']['media_type'] == 'image/jpeg'
    for reason in ('refusal', 'max_tokens'):
        response.stop_reason = reason
        with pytest.raises(PhotoUnavailable):
            grader.grade(b'image', snapshot)
    response.stop_reason = 'end_turn'
    response.content[0].text = '{bad json'
    with pytest.raises(PhotoUnavailable):
        grader.grade(b'image', snapshot)


def grade_start(store, done):
    return store.grade(OWNER, 'start', attempt_id=done['attempt']['id'], lease_id=str(uuid.uuid4()))


def test_durable_grading_leases_duplicates_and_quota(answer_store):
    store = answer_store
    done = finish(store, begin(store, request(store)))
    aid = done['attempt']['id']
    with ThreadPoolExecutor(2) as pool:
        grades = list(pool.map(lambda _: grade_start(store, done), range(2)))
    assert grades[0]['id'] == grades[1]['id']
    g = grades[0]
    with store.connect() as c:
        c.execute("update math_answer_grades set lease_until=now()-interval '1 second'")
    assert store.grade(OWNER, 'get', attempt_id=aid)['state'] == 'failed'
    newer = grade_start(store, done)
    with pytest.raises(ScanError, match='grading_interrupted'):
        store.grade(OWNER, 'complete', attempt_id=aid, lease_id=g['lease_id'], result=validate_assessment(assessment()))
    result = validate_assessment(assessment())
    completed = store.grade(OWNER, 'complete', attempt_id=aid, lease_id=newer['lease_id'], result=result)
    assert completed['state'] == 'completed'
    assert grade_start(store, done)['id'] == completed['id']
    assert store.grade(OWNER, 'get', attempt_id=aid)['result'] == result
    with pytest.raises(ScanError) as exc:
        store.grade(OTHER, 'get', attempt_id=aid)
    assert exc.value.status == 404
    # Only the owner-checked service RPC can read grades or mutate credit.
    import psycopg
    with store.connect() as c:
        c.execute('set role authenticated')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('select * from math_answer_grades')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select math_grade_action(%s,'get',%s::jsonb)", (OWNER, json.dumps({'attempt_id': aid})))
    # Failed checks count toward the durable daily allowance too.
    other_done = finish(store, begin(store, request(store, question='second')))
    for _ in range(18):
        pending = grade_start(store, other_done)
        store.grade(OWNER, 'fail', attempt_id=other_done['attempt']['id'], lease_id=pending['lease_id'])
    with pytest.raises(ScanError) as exc:
        grade_start(store, other_done)
    assert (exc.value.status, exc.value.code) == (429, 'grading_limit')
    # A cached completed check remains available after the daily allowance is spent.
    assert grade_start(store, done)['id'] == completed['id']


def test_grade_api_ownership_failure_retry_cache_and_restart(answer_store, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    store = answer_store
    done = finish(store, begin(store, request(store)))
    aid = done['attempt']['id']
    draft = attempt(store, question='not-submitted')['attempt']['id']
    app = create_app(auth=ScanAuth()); app.state.answers = store
    calls = []
    class Grader:
        def grade(self, image, snapshot):
            calls.append((image, snapshot))
            if len(calls) == 1:
                raise PhotoUnavailable('temporary failure')
            return validate_assessment(assessment())
    app.state.answer_grader = Grader()
    async def check():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://test',
                                     headers={'Authorization': f'Bearer {OWNER}'}) as c:
            url = f'/api/math/answer-attempts/{aid}/grade'
            assert (await c.post(url, headers={'Authorization': f'Bearer {OTHER}'})).status_code == 404
            assert (await c.post(url, headers={'Authorization': ''})).status_code == 401
            assert (await c.post('/api/math/answer-attempts/invalid/grade')).status_code == 404
            assert (await c.post(f'/api/math/answer-attempts/{draft}/grade')).status_code == 409
            assert not calls
            monkeypatch.delenv('ANTHROPIC_API_KEY')
            assert (await c.post(url)).status_code == 503
            assert store.grade(OWNER, 'get', attempt_id=aid) is None
            monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
            assert (await c.post(url)).status_code == 503
            failed = (await c.get(f'/api/math/answer-attempts/{aid}')).json()
            assert failed['grading']['state'] == 'failed' and failed['attachment']
            result = (await c.post(url, json={'snapshot': {'question': 'forged'}, 'score': 100})).json()
            assert result['grading']['result']['verdict'] == 'correct'
            assert 'lease_id' not in result['grading'] and 'object_key' not in result['attachment']
            assert (await c.post(url)).json()['grading']['id'] == result['grading']['id']
            assert len(calls) == 2 and calls[-1][1] == done['attempt']['snapshot']
            monkeypatch.delenv('ANTHROPIC_API_KEY')
            assert (await c.post(url)).json()['grading']['id'] == result['grading']['id']
        restarted = create_app(auth=ScanAuth()); restarted.state.answers = store
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url='http://test',
                                     headers={'Authorization': f'Bearer {OWNER}'}) as c:
            assert (await c.get(f'/api/math/answer-attempts/{aid}')).json()['grading']['result']['score'] == 100
    asyncio.run(check())


def test_in_progress_check_is_visible_and_duplicate_does_not_call_ai(answer_store, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'test-key')
    store = answer_store
    done = finish(store, begin(store, request(store)))
    aid = done['attempt']['id']
    app = create_app(auth=ScanAuth()); app.state.answers = store
    started, release = threading.Event(), threading.Event()
    class Grader:
        calls = 0
        def grade(self, image, snapshot):
            self.calls += 1; started.set()
            assert release.wait(timeout=10)
            return validate_assessment(assessment())
    app.state.answer_grader = Grader()
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test',
                                     headers={'Authorization': f'Bearer {OWNER}'}) as c:
            url = f'/api/math/answer-attempts/{aid}/grade'
            first = asyncio.create_task(c.post(url))
            assert await asyncio.to_thread(started.wait, 5)
            try:
                assert (await c.get(f'/api/math/answer-attempts/{aid}')).json()['grading']['state'] == 'grading'
                duplicate = await c.post(url)
                assert duplicate.json()['grading']['state'] == 'grading'
                assert app.state.answer_grader.calls == 1
            finally:
                release.set()
            assert (await first).json()['grading']['state'] == 'completed'
    asyncio.run(check())
