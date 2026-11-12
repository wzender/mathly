"""A store that remembers slow-changing reads (classes, members, roles, tests, assignments) for a short time.

Any change made through it to one of those forgets everything remembered at once. Rows come back as copies.
"""
from __future__ import annotations

import copy
import threading
import time

READS = frozenset({
    "classes", "classes_of_student", "classes_taught", "members", "get_class", "roles_of",
    "tests_of_classes", "get_test", "assignments_of_classes", "get_assignment", "all_students", "accounts", "curriculum",
    "subjects",
})
CHANGES = frozenset({
    "create_class", "update_class", "delete_class", "add_member", "remove_member", "give_role", "take_role", "link_user",
    "create_test", "update_test", "remove_test", "create_assignment", "remove_assignment", "set_lesson_dates",
    "create_subject", "update_subject", "delete_subject", "create_lesson", "save_lesson", "delete_lesson",
})


def _key(name: str, args: tuple, kwargs: dict):
    def freeze(v):
        if isinstance(v, (set, frozenset)):
            return tuple(sorted(v, key=repr))
        if isinstance(v, (list, tuple)):
            return tuple(freeze(x) for x in v)
        return v
    return name, freeze(args), tuple(sorted((k, freeze(v)) for k, v in kwargs.items()))


class CachedStore:
    def __init__(self, store, seconds: float, clock=time.monotonic) -> None:
        self._store, self._seconds, self._clock = store, seconds, clock
        self._lock = threading.Lock()
        self._kept: dict = {}            # key -> (expires, value)
        self._generation = 0             # bumped by every change, so a read that began before one is not kept

    def forget(self) -> None:
        with self._lock:
            self._kept.clear()
            self._generation += 1

    def __getattr__(self, name: str):
        target = getattr(self._store, name)
        if self._seconds <= 0 or not callable(target):
            return target
        if name in CHANGES:
            def change(*args, **kwargs):
                try:
                    return target(*args, **kwargs)
                finally:
                    self.forget()
            return change
        if name in READS:
            def read(*args, **kwargs):
                key = _key(name, args, kwargs)
                now = self._clock()
                with self._lock:
                    hit = self._kept.get(key)
                    if hit and hit[0] > now:
                        return copy.deepcopy(hit[1])
                    generation = self._generation
                value = target(*args, **kwargs)
                with self._lock:
                    if generation == self._generation:
                        self._kept[key] = (now + self._seconds, copy.deepcopy(value))
                return value
            return read
        return target
