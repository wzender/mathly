# Proposal

## Why

Each wait for the remote database costs 0.4 to 0.9 seconds from where the server runs, and the teacher's screens need 4 or 5 waits in a row (the tab numbers alone take 1.6 s). Most of what those waits read, the classes, their students, the roles, the tests and the assignments, changes rarely. And every screen starts blank until its data arrives.

## What Changes

- **The server remembers slow-changing facts for a short time** (30 seconds, set by `MATHLY_CACHE_SECONDS`, 0 turns it off): classes, class members, roles, tests and assignments. Any change made through the app to one of them forgets the remembered copy at once, so the person who made it never sees an old copy.
- **A screen opened again shows what it last knew, at once**, and refreshes it in the background: the tab numbers, the teacher's tabs, and the student's home, path, submissions and grades. A change the person makes clears what was remembered, so an old copy is never shown after their own action; and a refresh never redraws over something being typed.
- The teacher's counts ask for their tests and assignments together (one wait instead of two).

## Capabilities

### New Capabilities

### Modified Capabilities
- `app-basics`: "Slow-changing facts are remembered briefly" and "A screen shows what it last knew".

## Impact

- A new `mathly2/cached.py` around the Supabase store, a setting, `mathly2/assignments.py` (counts), and in the browser `api.js` plus the screens' `show` functions. No database change. PRD 7.3.
- One server process is assumed (a Space is one): with several, a change made through another process could show up late by the remembering time.
