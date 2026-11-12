"""The bank the app serves: the math content file plus the lessons published in the database (add-subjects-and-worksheets).

The file's bank is kept as `app.state.base_bank`. `rebuild` reads the subjects and the published lessons and swaps a new merged
bank into `app.state.bank` in one step, at start-up and after every publish, unpublish or reorder, so a change reaches students
without a restart; a request already running keeps the bank it started with. When the database cannot be read (the subjects
migration not applied yet, or the database down at start-up) the file's lessons are served alone and the reason is kept in
`app.state.content_error` for the content screens. If building a new bank fails, the bank already served stays.
"""
from __future__ import annotations

import logging

from .bank import Bank, merge

log = logging.getLogger("mathly2.content")


def _raw(store):
    return getattr(store, "_store", store)                  # past the short cache: a change must show at once


def rebuild(app) -> Bank:
    """Build and serve the merged bank. Returns the bank now served. Raises only if building fails while the database answered."""
    base = app.state.base_bank
    try:
        store = _raw(app.state.store)
        subjects, lessons = store.subjects(), store.published_lessons()
    except Exception as exc:                                 # missing tables or no database: the file's lessons, math only
        log.warning("subjects and lessons could not be read, serving the content file only: %s", exc)
        app.state.content_error = str(exc) or type(exc).__name__
        if not hasattr(app.state, "bank") or app.state.bank is base:
            app.state.bank = Bank(merge(base.data, [], []))
        return app.state.bank
    bank = Bank(merge(base.data, subjects, lessons, log=log.warning))
    app.state.bank = bank
    app.state.content_error = None
    return bank
