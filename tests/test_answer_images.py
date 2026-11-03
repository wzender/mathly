"""Answer images in a private Hugging Face bucket (app/answer_scans.py): which store each image is in, and cleanup.
The bucket here is a stand-in; nothing leaves the machine."""
import json
import urllib.parse
import pytest

from app.answer_scans import AnswerScans, HubImages, ScanError, on_hub


class Auth:
    url, secret = "https://example.supabase.co", "service-key"


class FakeHub:
    def __init__(self):
        self.files, self.old = {}, set()

    def put(self, key, data): self.files[key] = data

    def read(self, key):
        if key not in self.files:
            raise ScanError(404, "not_found")
        return self.files[key]

    def delete(self, key): self.files.pop(key, None)

    def older_than(self, age): return [k for k in self.files if k in self.old]


class Store(AnswerScans):
    """The adapter with Supabase's HTTP calls recorded instead of sent."""
    def __init__(self, images, referenced=(), candidates=()):
        super().__init__(Auth(), enabled=True, images=images)
        self.calls, self._referenced, self._candidates = [], set(referenced), list(candidates)

    def _request(self, path, method="GET", data=None, content_type=None):
        self.calls.append((method, path))
        if path.startswith("/rest/v1/math_answer_attachments"):
            return json.dumps([{"object_key": k} for k in self._referenced if f'"{k}"' in urllib.parse.unquote(path)]).encode()
        return b"supabase-image"

    def action(self, user_id, action, **data):
        assert action == "cleanup_candidates"
        return self._candidates


def test_new_images_are_named_for_the_bucket_and_kept_there():
    hub = FakeHub(); store = Store(hub)
    key = store.new_key("u1", "s1", "l1")
    assert key.startswith("u1/s1/l1/hf-") and key.endswith(".jpg") and on_hub(key)
    store.put(key, b"jpeg")
    assert hub.files == {key: b"jpeg"} and store.calls == []   # no Supabase Storage call at all
    assert store.read(key) == b"jpeg"
    store.delete(key)
    assert hub.files == {} and store.calls == []


def test_images_saved_before_the_bucket_are_still_read_from_supabase():
    store = Store(FakeHub())
    assert store.read("u1/s1/l1/1234.jpg") == b"supabase-image"
    assert store.calls == [("GET", "/storage/v1/object/authenticated/mathly-answers/u1/s1/l1/1234.jpg")]


def test_without_a_bucket_everything_stays_in_supabase():
    store = Store(None)
    key = store.new_key("u1", "s1", "l1")
    assert not on_hub(key)
    store.put(key, b"jpeg")
    assert store.calls[0][0] == "POST" and store.calls[0][1].startswith("/storage/v1/object/mathly-answers/u1/s1/l1/")
    with pytest.raises(ScanError) as err:   # a bucket image while the bucket is off: unavailable, not a Supabase 404
        store.read("u1/s1/l1/hf-x.jpg")
    assert err.value.status == 503


def test_cleanup_removes_old_bucket_images_no_answer_uses():
    hub = FakeHub()
    kept, orphan, fresh = "u/s/l/hf-kept.jpg", "u/s/l/hf-orphan.jpg", "u/s/l/hf-fresh.jpg"
    for k in (kept, orphan, fresh):
        hub.put(k, b"x")
    hub.old = {kept, orphan}   # fresh is less than a day old: its answer may still be on its way
    store = Store(hub, referenced={kept}, candidates=["u/s/l/old-supabase.jpg"])
    assert store.cleanup() == 2   # the Supabase orphan and the bucket orphan
    assert set(hub.files) == {kept, fresh}
    assert ("DELETE", "/storage/v1/object/mathly-answers") in store.calls


def test_the_bucket_is_configured_from_the_environment(monkeypatch):
    monkeypatch.setenv("MATHLY_ANSWER_BUCKET", "")
    assert HubImages.from_env() is None
    monkeypatch.setenv("MATHLY_ANSWER_BUCKET", "someone/answers")
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    hub = HubImages.from_env()
    assert hub.bucket == "someone/answers" and hub.api.token == "hf_test"
