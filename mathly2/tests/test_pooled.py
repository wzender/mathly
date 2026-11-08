"""Reused connections to the database (fewer-database-calls 1.3), against a small local server."""
import json
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from mathly2 import pooled


class Server:
    """A keep-alive HTTP/1.1 server that counts the connections it accepted and the requests it answered."""

    def __init__(self, close_after: int | None = None, status: int = 200, body: bytes = b'[{"ok": true}]', delay: float = 0.0):
        outer = self
        self.connections = self.requests = 0
        self.lock = threading.Lock()

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                with outer.lock:
                    outer.connections += 1
                self.served = 0

            def do_GET(self):
                self.answer()

            do_POST = do_GET

            def answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                if delay:
                    import time
                    time.sleep(delay)
                self.served += 1
                with outer.lock:
                    outer.requests += 1
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                if close_after and self.served >= close_after:
                    self.close_connection = True                      # hang up after this answer without saying so (an idle timeout)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server():
    made = []

    def make(**kw):
        made.append(Server(**kw))
        return made[-1]
    yield make
    for s in made:
        s.stop()


def test_several_calls_reuse_one_connection(server):
    s = server()
    for _ in range(5):
        status, body = pooled.request("GET", s.url + "/rest/v1/x?a=1")
        assert status == 200 and json.loads(body) == [{"ok": True}]
    assert s.requests == 5 and s.connections == 1


def test_a_write_sends_its_body_and_reuses_the_connection(server):
    s = server()
    pooled.request("GET", s.url + "/a")
    status, _ = pooled.request("POST", s.url + "/b", {"Content-Type": "application/json"}, b'{"x": 1}')
    assert status == 200 and s.connections == 1


def test_each_thread_has_its_own_connection(server):
    s = server()
    pooled.request("GET", s.url + "/a")
    done = []
    threading.Thread(target=lambda: done.append(pooled.request("GET", s.url + "/b")[0])).start()
    for _ in range(100):
        if done:
            break
        threading.Event().wait(0.02)
    assert done == [200] and s.connections == 2


def test_a_connection_the_server_closed_is_replaced_once_and_the_call_still_works(server):
    s = server(close_after=1)                                         # the server hangs up after every answer
    for _ in range(3):
        status, _ = pooled.request("GET", s.url + "/a")
        assert status == 200
    assert s.requests == 3 and s.connections >= 2


def test_an_answer_of_400_or_more_raises_an_http_error_with_a_body_that_can_be_read(server):
    s = server(status=409, body=b'{"message": "duplicate key"}')
    with pytest.raises(urllib.error.HTTPError) as caught:
        pooled.request("POST", s.url + "/a", None, b"{}")
    assert caught.value.code == 409 and json.loads(caught.value.read())["message"] == "duplicate key"
    ok = server()                                                      # a failed answer leaves the client usable
    assert pooled.request("GET", ok.url + "/a")[0] == 200


def test_a_connection_that_fails_is_a_url_error_and_a_slow_server_a_timeout(server):
    with pytest.raises(urllib.error.URLError):
        pooled.request("GET", "http://127.0.0.1:1/never")
    slow = server(delay=1.0)
    with pytest.raises(TimeoutError):
        pooled.request("GET", slow.url + "/a", timeout=0.2)
    assert pooled.request("GET", slow.url + "/a", timeout=5)[0] == 200      # the broken connection was dropped; the next call works


def test_the_store_and_the_authenticator_use_the_pooled_client(server):
    from mathly2.auth import SupabaseAuthenticator
    from mathly2.store import SupabaseStore
    s = server(body=b'[{"id": 1, "name": "A", "lessons": [], "teacher_email": null, "ai_enabled": false, "ai_daily_checks": 150, "created_by": "x", "created_at": "2026-11-01T00:00:00+00:00", "students": 0}]')
    store = SupabaseStore(s.url, "secret")
    for _ in range(3):
        store._request("GET", "m2_classes", {"select": "*"})
    assert s.requests == 3 and s.connections == 1
    user = server(body=b'{"id": "u1", "email": "a@school.test", "email_confirmed_at": "2026-01-01"}')
    auth = SupabaseAuthenticator(user.url, "key")
    assert auth.user("token-1") == {"id": "u1", "email": "a@school.test"}
    assert auth.user("token-2") == {"id": "u1", "email": "a@school.test"} and user.requests == 2 and user.connections == 1
