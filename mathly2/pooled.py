"""HTTP calls that reuse their connection. A new secure connection costs several round trips before the first byte; with a remote database that
is most of a call. Each thread keeps one open connection per host and reuses it; when the server closed an idle one, the call is made again
once on a fresh connection. Errors look like urllib's (HTTPError for an answer of 400 or more, URLError for a connection that failed), so
callers that handled urllib keep working."""
from __future__ import annotations

import http.client
import io
import socket
import threading
import urllib.error
import urllib.parse

_local = threading.local()
STALE = (http.client.RemoteDisconnected, http.client.CannotSendRequest, http.client.ResponseNotReady, BrokenPipeError, ConnectionResetError,
         ConnectionAbortedError)


def _connection(url: urllib.parse.ParseResult, timeout: float) -> tuple[http.client.HTTPConnection, bool]:
    """This thread's connection to the host (made if there is none), and whether it is an old one being reused."""
    pool = _local.__dict__.setdefault("pool", {})
    key = (url.scheme, url.netloc)
    conn = pool.get(key)
    if conn is not None:
        conn.timeout = timeout
        if conn.sock is not None:
            conn.sock.settimeout(timeout)
        return conn, True
    cls = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    conn = pool[key] = cls(url.netloc, timeout=timeout)
    return conn, False


def _drop(url: urllib.parse.ParseResult) -> None:
    conn = _local.__dict__.setdefault("pool", {}).pop((url.scheme, url.netloc), None)
    if conn is not None:
        conn.close()


def request(method: str, url: str, headers: dict | None = None, body: bytes | None = None, timeout: float = 10) -> tuple[int, bytes]:
    """(status, body) of a call, raising urllib.error.HTTPError for 400 and above and URLError for a connection that failed."""
    parts = urllib.parse.urlparse(url)
    path = parts.path + (f"?{parts.query}" if parts.query else "")
    for attempt in (1, 2):
        conn, reused = _connection(parts, timeout)
        try:
            conn.request(method, path or "/", body=body, headers=headers or {})
            response = conn.getresponse()
            data = response.read()
            if response.getheader("Connection", "").lower() == "close":
                _drop(parts)
            break
        except STALE as exc:
            _drop(parts)
            if reused and attempt == 1:                              # the server had closed an idle connection: once more, on a new one
                continue
            raise urllib.error.URLError(exc) from exc
        except (socket.timeout, TimeoutError) as exc:
            _drop(parts)
            raise TimeoutError(str(exc)) from exc
        except (OSError, http.client.HTTPException) as exc:
            _drop(parts)
            raise urllib.error.URLError(exc) from exc
    if response.status >= 400:
        raise urllib.error.HTTPError(url, response.status, response.reason, response.msg, io.BytesIO(data))
    return response.status, data
