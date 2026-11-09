"""Run the app on a free port in a background thread, for browser tests."""
from __future__ import annotations

import socket
import threading
import time
from contextlib import contextmanager

import uvicorn


@contextmanager
def running(app):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def offline_formulas(page):
    """For tests that show no formulas: do not wait for the formula library from the network (a slow CDN made them time out)."""
    page.route("**/mathjax@*/**", lambda route: route.abort())
    return page


def only(bank, lessons):
    """A bank with just these lessons (and their skills), for tests that want a short path: every class now studies the whole bank."""
    from mathly2.bank import Bank
    keep = set(lessons)
    return Bank({**bank.data, "units": [u for u in bank.lessons if u["id"] in keep], "skills": [s for s in bank.skills if s["unit"] in keep]})
