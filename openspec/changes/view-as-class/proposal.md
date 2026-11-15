# Proposal

## Why

A developer or a teacher who opens the student view is in no class, so the student screens show no tests, assignments or readiness: they
cannot check what the students of a class see (a new test on home, its lessons).

## What Changes

- "תצוגה ככיתה": a picker on top of the student screens for a developer or a teacher who is in no class. A developer can pick any class, a teacher the classes they teach.
- With a class picked, the student screens show that class's tests, assignments, subjects and photo help; progress, stars and readiness stay the viewer's own.
- The choice is kept on the device and sent with every request (`X-View-Class`); the server checks it. A student's own classes are never replaced.

## Capabilities

### New Capabilities

### Modified Capabilities
- `accounts-and-classes`: previewing the student screens as a class.

## Impact

- `access.py` (`my_classes`, `preview_classes`), its use in `realtests.py`, `assignments.py`, `ai_help.py`, `skills.py`; `/api/me` returns `preview`. `static/api.js`, `static/student.js`.
