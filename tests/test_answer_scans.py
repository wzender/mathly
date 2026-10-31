import asyncio
import io
import uuid
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from PIL import Image, ImageDraw

from app.answer_scans import ScanError, clean_image
from app.main import create_app
from scan_support import OWNER, OTHER, ScanAuth, answer_store, postgres_server


def png():
    out = io.BytesIO()
    image = Image.new('RGB', (320, 240), 'white')
    pen = ImageDraw.Draw(image)
    pen.line([(35, 30), (35, 150), (250, 150), (35, 30)], fill='navy', width=3)
    pen.text((12, 80), '6', fill='navy'); pen.text((135, 160), '8', fill='navy')
    pen.text((35, 195), '6 x 8 / 2 = 24 cm2', fill='navy')
    image.save(out, 'PNG')
    return out.getvalue()


def attempt(store, owner=OWNER, version='v1', question='geometry'):
    return store.action(owner, 'resume', question_id=question, question_version=version,
                        snapshot={'question': 'Draw your proof', 'type': 'open-ended'})


def request(store, owner=OWNER, **kwargs):
    a = attempt(store, owner, **kwargs)
    return store.action(owner, 'create_scan', attempt_id=a['attempt']['id'])


def begin(store, result, key=None):
    sid = result['scan']['id']
    store.action(OWNER, 'confirm', scan_id=sid)
    return store.action(OWNER, 'begin', scan_id=sid, key=key or str(uuid.uuid4()))


def finish(store, result):
    s = result['scan']
    key = f"{OWNER}/{s['id']}/{s['lease_id']}/{uuid.uuid4()}.jpg"
    store.put(key, clean_image(png(), 'image/png'))
    return store.action(OWNER, 'finalize', scan_id=s['id'], lease_id=s['lease_id'], object_key=key, byte_size=500)


def test_additive_migration_rls_and_service_only_rpc(answer_store):
    import psycopg
    store = answer_store
    mine = request(store)
    finish(store, begin(store, mine))
    request(store, OTHER)
    with store.connect() as c:
        assert c.execute('select name from classes').fetchone()[0] == 'existing math class'
        assert c.execute("select public from storage.buckets where id='mathly-answers'").fetchone()[0] is False
        c.execute('set role authenticated')
        c.execute("select set_config('request.jwt.claim.sub',%s,false)", (OWNER,))
        rows = c.execute('select user_id from math_question_attempts').fetchall()
        assert [str(row[0]) for row in rows] == [OWNER]
        assert len(c.execute('select id from math_answer_scans').fetchall()) == 1
        assert len(c.execute('select id from math_answer_attachments').fetchall()) == 1
        c.execute("select set_config('request.jwt.claim.sub',%s,false)", (OTHER,))
        assert c.execute('select id from math_answer_attachments').fetchall() == []
        c.execute("select set_config('request.jwt.claim.sub',%s,false)", (OWNER,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("select public.math_answer_action(%s,'get',%s::jsonb)", (OTHER, '{}'))
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("update math_answer_scans set state='received'")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute("insert into storage.objects(bucket_id,name) values('mathly-answers','foreign')")
        assert c.execute("select * from storage.objects where bucket_id='mathly-answers'").fetchall() == []
        c.execute('set role anon')
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            c.execute('select * from math_answer_scans')
    with pytest.raises(ScanError) as e:
        store.action(OTHER, 'get', attempt_id=mine['attempt']['id'])
    assert e.value.status == 404


def test_attempt_resume_version_and_generation(answer_store):
    store = answer_store
    a = attempt(store)
    assert attempt(store)['attempt']['id'] == a['attempt']['id']
    assert attempt(store, version='v2')['attempt']['id'] != a['attempt']['id']
    r = store.action(OWNER, 'create_scan', attempt_id=a['attempt']['id'])
    assert store.action(OWNER, 'create_scan', attempt_id=a['attempt']['id'])['scan']['id'] == r['scan']['id']
    with pytest.raises(ScanError):
        store.action(OWNER, 'create_scan', attempt_id=a['attempt']['id'], question_id='forged')
    with store.connect() as c:
        c.execute("update math_answer_scans set expires_at=now()-interval '1 second' where id=%s", (r['scan']['id'],))
    assert store.action(OWNER, 'get', scan_id=r['scan']['id'])['scan']['state'] == 'expired'
    new = store.action(OWNER, 'create_scan', attempt_id=a['attempt']['id'], renew=True)
    assert new['scan']['generation'] == 2
    with pytest.raises(ScanError, match='superseded'):
        store.action(OWNER, 'confirm', scan_id=r['scan']['id'])


def test_concurrent_uploads_and_lost_response(answer_store):
    store = answer_store
    r = request(store)
    with pytest.raises(ScanError, match='confirmation_required'):
        store.action(OWNER, 'begin', scan_id=r['scan']['id'], key=str(uuid.uuid4()))
    b = begin(store, r)
    assert store.action(OWNER, 'begin', scan_id=r['scan']['id'], key=b['scan']['idempotency_key'])['scan']['lease_id'] == b['scan']['lease_id']
    with pytest.raises(ScanError, match='upload_in_progress'):
        store.action(OWNER, 'begin', scan_id=r['scan']['id'], key=str(uuid.uuid4()))
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: finish(store, b), range(2)))
    assert results[0]['attachment']['id'] == results[1]['attachment']['id']
    assert results[0]['attempt']['status'] == 'received'
    with store.connect() as c:
        assert c.execute('select count(*) from math_answer_attachments').fetchone()[0] == 1
    assert store.action(OWNER, 'create_scan', attempt_id=r['attempt']['id'], renew=True)['scan']['id'] == r['scan']['id']


def test_stale_lease_and_renewal_reject_late_completion(answer_store):
    store = answer_store
    b = begin(store, request(store))
    with store.connect() as c:
        c.execute("update math_answer_scans set lease_until=now()-interval '1 second' where id=%s", (b['scan']['id'],))
    assert store.action(OWNER, 'pending')[0]['scan']['state'] == 'failed'
    store.action(OWNER, 'create_scan', attempt_id=b['attempt']['id'], renew=True)
    with pytest.raises(ScanError, match='superseded'):
        finish(store, b)
    assert store.action(OWNER, 'get', attempt_id=b['attempt']['id'])['attachment'] is None


def test_cleanup_retains_committed_images_and_removes_deleted_attempts(answer_store):
    store = answer_store
    done = finish(store, begin(store, request(store)))
    store.put('orphan.jpg', b'orphan')
    with store.connect() as c:
        c.execute("update storage.objects set created_at=now()-interval '25 hours'")
    assert store.cleanup() == 1
    assert store.read(done['attachment']['object_key'])
    with store.connect() as c:
        c.execute('delete from math_question_attempts where id=%s', (done['attempt']['id'],))
    assert store.cleanup() == 1


def test_image_validation_and_exif_removal():
    assert Image.open(io.BytesIO(clean_image(png(), 'image/png'))).format == 'JPEG'
    for data, mime, status in [(b'fake', 'image/jpeg', 415), (b'', 'image/png', 400),
                               (b'x' * 5_000_001, 'image/jpeg', 413), (png(), 'image/heic', 415)]:
        with pytest.raises(ScanError) as e:
            clean_image(data, mime)
        assert e.value.status == status
    image = Image.new('RGB', (30, 60))
    exif = Image.Exif(); exif[274] = 6; exif[270] = 'private'
    raw = io.BytesIO(); image.save(raw, 'JPEG', exif=exif)
    result = Image.open(io.BytesIO(clean_image(raw.getvalue(), 'image/jpeg')))
    assert result.size == (60, 30) and not result.getexif()


def test_scan_api_end_to_end_failure_retry_and_restart(answer_store, monkeypatch):
    import copy
    from app.math_skills import algebra9, question_version
    graph = copy.deepcopy(algebra9())
    graph['skills'][0]['sample'] = {'type': 'open-ended', 'question': 'Draw a proof', 'version': 1}
    monkeypatch.setattr('app.answer_routes.algebra9', lambda: graph)
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    store = answer_store
    app = create_app(auth=ScanAuth()); app.state.answers = store
    owner = {'Authorization': f'Bearer {OWNER}'}
    other = {'Authorization': f'Bearer {OTHER}'}
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers=owner) as c:
            assert (await c.get('/api/me')).json()['answer_scans'] is True
            assert (await c.post('/api/math/answer-attempts', json={'question_id': 'forged'})).status_code == 404
            assert (await c.post('/api/math/answer-attempts', json={'question_id': graph['skills'][0]['id'], 'question_version': 'bad'})).status_code == 409
            assert (await c.post('/api/math/answer-attempts', json={'question_id': graph['skills'][0]['id']})).status_code == 409
            result = (await c.post('/api/math/answer-attempts', json={'question_id': graph['skills'][0]['id'],
                         'question_version': question_version(graph['skills'][0]['sample'])})).json()
            aid = result['attempt']['id']
            result = (await c.post(f'/api/math/answer-attempts/{aid}/scans', json={})).json()
            sid = result['scan']['id']
            assert 'lease_id' not in result['scan']
            assert (await c.get(f'/api/math/answer-scans/{sid}', headers=other)).status_code == 404
            assert (await c.get('/api/math/answer-scans', headers=other)).json() == []
            assert (await c.get(f'/api/math/answer-attempts/{aid}/image', headers=other)).status_code == 404
            assert (await c.post(f'/api/math/answer-scans/{sid}/confirm')).status_code == 200
            async def lease():
                return (await c.post(f'/api/math/answer-scans/{sid}/uploads', json={'key': str(uuid.uuid4())})).json()['lease_id']
            lid = await lease()
            url = f'/api/math/answer-scans/{sid}/uploads/{lid}'
            assert (await c.post(url, files={'photo': ('fake.jpg', b'fake', 'image/jpeg')})).status_code == 415
            assert (await c.get(f'/api/math/answer-scans/{sid}')).json()['scan']['state'] == 'failed'
            for failure in ('fail_put', 'fail_finalize'):
                lid = await lease(); url = f'/api/math/answer-scans/{sid}/uploads/{lid}'
                setattr(store, failure, True)
                assert (await c.post(url, files={'photo': ('answer.png', png(), 'image/png')})).status_code == 503
                setattr(store, failure, False)
                assert (await c.get(f'/api/math/answer-scans/{sid}')).json()['attachment'] is None
            lid = await lease(); url = f'/api/math/answer-scans/{sid}/uploads/{lid}'
            result = (await c.post(url, files={'photo': ('answer.png', png(), 'image/png')})).json()
            assert result['scan']['state'] == 'received' and 'object_key' not in result['attachment']
            assert (await c.post(url, files={'photo': ('answer.png', png(), 'image/png')})).json()['attachment']['id'] == result['attachment']['id']
            image = await c.get(f'/api/math/answer-attempts/{aid}/image')
            assert image.status_code == 200 and image.headers['cache-control'] == 'no-store'
            restarted = create_app(auth=ScanAuth()); restarted.state.answers = store
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=restarted), base_url='http://test', headers=owner) as new:
                assert (await new.get(f'/api/math/answer-attempts/{aid}/image')).content == image.content
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url='http://test') as guest:
            assert (await guest.get('/api/math/answer-scans')).status_code == 401
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as guest:
            assert (await guest.get('/api/math/answer-scans')).status_code == 401
    asyncio.run(check())


def test_expired_scan_rejects_begin_and_submission_and_can_renew(answer_store):
    store = answer_store
    r = request(store)
    b = begin(store, r)
    with store.connect() as c:
        c.execute("update math_answer_scans set expires_at=now()-interval '1 second' where id=%s", (r['scan']['id'],))
    app = create_app(auth=ScanAuth());app.state.answers=store
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test', headers={'Authorization':f'Bearer {OWNER}'}) as c:
            sid, lid = b['scan']['id'], b['scan']['lease_id']
            assert (await c.post(f'/api/math/answer-scans/{sid}/confirm')).status_code == 410
            assert (await c.post(f'/api/math/answer-scans/{sid}/uploads', json={'key':str(uuid.uuid4())})).status_code == 410
            assert (await c.post(f'/api/math/answer-scans/{sid}/uploads/{lid}', files={'photo':('a.png',png(),'image/png')})).status_code == 410
            renewed = (await c.post(f"/api/math/answer-attempts/{r['attempt']['id']}/scans",json={'renew':True})).json()
            assert renewed['attempt']['id'] == r['attempt']['id'] and renewed['scan']['generation']==2
            assert (await c.post(f'/api/math/answer-scans/{sid}/confirm')).status_code == 409
    asyncio.run(check())


def test_enable_rollback_preserves_received_answers(answer_store):
    store = answer_store
    done = finish(store, begin(store, request(store)))
    store.enabled = False
    app = create_app(auth=ScanAuth());app.state.answers=store
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test',headers={'Authorization':f'Bearer {OWNER}'}) as c:
            assert (await c.get('/api/me')).json()['answer_scans'] is False
            skills=(await c.get('/api/math/skills')).json()['skills']
            assert len(next(s for s in skills if s['id']=='a_30_side')['sample']['choices'])==3
            assert (await c.get('/api/math/answer-scans')).status_code==503
            store.enabled=True
            skills=(await c.get('/api/math/skills')).json()['skills']
            assert next(s for s in skills if s['id']=='a_30_side')['sample']['type']=='open-ended'
            assert (await c.get(f"/api/math/answer-attempts/{done['attempt']['id']}/image")).status_code==200
        with store.connect() as c:
            assert c.execute('select count(*) from classes').fetchone()[0]==1
            assert c.execute('select count(*) from math_answer_attachments').fetchone()[0]==1
    asyncio.run(check())


def test_supabase_storage_http_contract(monkeypatch):
    import json
    from urllib.error import HTTPError
    from app.answer_scans import AnswerScans
    store = AnswerScans(ScanAuth(), enabled=True)
    requests=[]
    class Response:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self): return b'{}'
    def urlopen(req, timeout):
        requests.append(req)
        return Response()
    monkeypatch.setattr('urllib.request.urlopen',urlopen)
    store.action(OWNER,'get',attempt_id=str(uuid.uuid4()))
    assert requests[-1].full_url.endswith('/rest/v1/rpc/math_answer_action')
    assert json.loads(requests[-1].data)['p_user']==OWNER
    key=f'{OWNER}/scan/lease/image.jpg'
    store.put(key,b'image');assert requests[-1].method=='POST' and requests[-1].full_url.endswith('/storage/v1/object/mathly-answers/'+key)
    assert requests[-1].get_header('Content-type')=='image/jpeg'
    store.read(key);assert requests[-1].full_url.endswith('/storage/v1/object/authenticated/mathly-answers/'+key)
    store.delete(key);assert requests[-1].method=='DELETE' and json.loads(requests[-1].data)=={'prefixes':[key]}
    assert all(r.get_header('Authorization')=='Bearer server-test' for r in requests)
    def denied(req, timeout):
        raise HTTPError(req.full_url,400,'bad',{},io.BytesIO(b'{"code":"P0002","message":"private detail"}'))
    monkeypatch.setattr('urllib.request.urlopen',denied)
    with pytest.raises(ScanError) as e:
        store.action(OTHER,'get',attempt_id=str(uuid.uuid4()))
    assert (e.value.status,e.value.code)==(404,'not_found')


def test_renewal_and_finalization_are_serialized(answer_store):
    store = answer_store
    b = begin(store, request(store))
    def renew():
        try:
            return store.action(OWNER,'create_scan',attempt_id=b['attempt']['id'],renew=True)
        except ScanError as exc:
            assert exc.code=='upload_in_progress'
    with ThreadPoolExecutor(2) as pool:
        finalizing=pool.submit(finish,store,b)
        renewing=pool.submit(renew)
        result=finalizing.result();renewing.result()
    assert result['scan']['state']=='received'
    assert store.action(OWNER,'get',attempt_id=b['attempt']['id'])['attachment']['id']==result['attachment']['id']
    with store.connect() as c:
        assert c.execute('select count(*) from math_answer_attachments').fetchone()[0]==1
        assert c.execute('select count(*) from math_answer_scans').fetchone()[0]==1
