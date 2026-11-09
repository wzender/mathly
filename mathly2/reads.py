"""Fewer waits for the database. A request that needs several facts asks for them together (`prefetch`: the ones that do not depend on
each other run at the same time), and a fact asked twice in one request is read once. Only reads go through here; a handler must not
read a fact again after writing it (it uses what it wrote)."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi import Request

POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="db")

READS = frozenset({"classes_of_student", "classes_taught", "progress_of", "last_answered", "daily_correct", "recent_skills", "attempts_of",
                   "tests_of_classes", "get_progress", "answers_of", "reward_state", "comets_of", "members", "get_class", "get_test", "roles_of", "assignments_of_classes", "submissions_of_user", "get_assignment", "get_submission", "curriculum"})


def _key(name: str, args: tuple) -> tuple:
    return (name, tuple(tuple(sorted(a)) if isinstance(a, (list, set, frozenset)) else a for a in args))


class Reads:
    """The reads of one request, each done once. Thread safe: `prefetch` fills it from several threads."""

    def __init__(self, store) -> None:
        self.store = store
        self._done: dict[tuple, object] = {}
        self._lock = threading.Lock()

    def _read(self, name: str, *args):
        key = _key(name, args)
        with self._lock:
            if key in self._done:
                return self._done[key]
        value = getattr(self.store, name)(*args)
        with self._lock:
            return self._done.setdefault(key, value)

    def __getattr__(self, name: str):
        if name in READS:
            return lambda *args: self._read(name, *args)
        raise AttributeError(name)

    def prefetch(self, *calls: tuple) -> None:
        """Start the reads (each `(name, *args)`) that are not done yet, together, and wait for all of them. The first error is raised."""
        missing = []
        with self._lock:
            for call in calls:
                if _key(call[0], call[1:]) not in self._done:
                    missing.append(call)
        if len(missing) == 1:
            self._read(missing[0][0], *missing[0][1:])
        elif missing:
            for future in [POOL.submit(self._read, c[0], *c[1:]) for c in missing]:
                future.result()


def of(request: Request) -> Reads:
    """The request's reads (made on first use)."""
    found = getattr(request.state, "reads", None)
    if found is None:
        found = request.state.reads = Reads(getattr(request.app.state, "store", None))
    return found
