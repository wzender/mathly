# Tasks

## 1. The server remembers

- [x] 1.1 Add `cached.py` (a wrapper around the Supabase store that remembers the reads of classes, members, roles, tests and assignments for `MATHLY_CACHE_SECONDS`, forgets everything at once on any change to them, never remembers an error, returns copies, and is not fooled by a read that was already running when a change happened) and use it for the real database; verify unit tests: a repeat read within the time is not asked again, the time passing asks again, each change forgets (create, update, remove for classes, members, roles, tests, assignments), a read that began before a change is not kept, answers and progress writes do not forget, 0 turns it off, and a returned row can be changed without changing the remembered one
- [x] 1.2 Make the teacher's counts ask for tests and assignments together, and measure the waits with the delay store wrapped in the cache; verify the timing test: the teacher's counts, assignments and tests tabs and the student's grades need fewer waits in a row the second time than the first, and a change shows at once

## 2. Screens that show what they last knew

- [x] 2.1 Add the remembering of GET answers to `api.js` (shown at once, refreshed in the background, forgotten on any change the person makes and on signing out, never redrawn over typing or an open detail) and use it for the teacher's tab numbers and tabs (classes, tests, assignments, inbox) and the student's home, path, submissions and grades; verify Playwright tests with a held request: going back to a tab shows its content and numbers at once, the new ones replace them when they arrive, grading shows no stale inbox, typing survives a refresh, and signing out clears it

## 3. Wrap-up

- [x] 3.1 Add the PRD line; run `venv/bin/python -m pytest mathly2/tests` and `openspec validate cache-and-instant-screens --strict`; verify both pass
