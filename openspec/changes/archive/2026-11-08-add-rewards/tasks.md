# Tasks

## 1. Daily goal and streak (already built, now covered by the spec's scenarios)

- [x] 1.1 Add the missing tests for the `rewards` scenarios on the existing rules and path: a fifth right answer shows the goal reached (also when one of the five came after opening help), a 4-day streak still shows 4 in the morning, a missed day restarts the streak at today, and the goal and streak are on the path screen in a browser; verify the tests pass without changing `learning.py`

## 2. Fading stars

- [x] 2.1 Add `last_answered(user_id)` (newest answer day per skill) to both stores; verify unit tests for each, that other students' answers do not count, and request tests for the Supabase store
- [x] 2.2 Add `faded` to `GET /api/path` and `GET /api/collection` (decision 1): true only for a mastered skill whose newest answer is 14 or more school days old; verify API tests for 13 days (not faded), 14 and 15 days (faded, still `mastered`), an answer on it relights it (right or wrong), a skill not mastered is never faded, and that readiness inputs (`state`, mastery counts, the lesson's `mastered` and `completed`) are the same with and without fading
- [x] 2.3 Show a faded star on the path: dimmed, "◌ דועך" under it and in its accessible name; verify a Playwright test that a faded star differs from a bright mastered one, says "דועך" in text and name, still counts in the hub's "נשלטו" figure, and relights after one answer

## 3. Comets: server

- [x] 3.1 Add `comets.py` with the twelve comets (id, symbol, name, fact, ported from mathly1) and `due(...)` (decision 3), plus the migration `20261109090000_m2_rewards.sql` for `m2_comets` and `m2_reward_state`, and the store methods to read and write them in both stores; verify unit tests of `due` with a fixed `rng` for every branch (all caught, already today, first comet only on the goal-reaching answer, 11% and 13% afterwards), migration tests on PostgreSQL, and that the twelve ids are unique
- [x] 3.2 Return `comet: true` from the answer route when due and store the day at that moment; verify API tests: five right answers give a comet on the fifth and not before, a second right answer the same day gives none, a wrong answer never does, a reload cannot give a second one, and an answer after all twelve are caught gives none
- [x] 3.3 Add `POST /api/comets/catch` and `GET /api/comets` (decisions 2 and 4); verify API tests: a catch adds a comet the student did not have, two catches in a row give one comet and a 409, a catch with no comet offered today is refused with 409, the twelve comets are all reachable over repeated days, and one student's comets are not another's; the permission matrix test is updated and passes

## 4. Comets: screens

- [x] 4.1 Draw the crossing comet and the catch card on the exercise screen (decision 5), with a still "☄ שביט!" button under reduced motion; verify a Playwright test that after the fifth right answer a comet crosses, a tap catches it and shows name and fact, answering stays possible while it crosses, no second comet comes the same day, and under reduced motion no animation runs and the still button appears once
- [x] 4.2 Add the reward drawings to `sky.js`: the comet, the comet card, and the constellation (port of `SHAPES`, `shape`, `along`, `onCorners`, with the fallback shape); verify a Playwright test that constellations of 2, 4 and 6 stars and the fallback fit a 360px screen with every star inside the picture

## 5. The collection

- [x] 5.1 Rewrite `collection.js` (decision 6): completed lessons as constellations, mastered skills as stars linking to them (faded ones dimmed with "דועך"), and the twelve comets, caught ones with symbol and name, missing ones as "?" with "עוד לא נתפס"; verify a Playwright test that mastering a lesson's last skill adds its constellation, three caught comets show three comets and nine "?", a caught comet opens its fact, and nothing scrolls sideways at 360px
- [x] 5.2 Update `docs/mockups/mathly2-screens.html` only if the collection tab no longer matches what was built; verify by opening it beside a screenshot of the collection

## 6. Wrap-up

- [x] 6.1 Walk the whole reward loop in a browser: a new student answers five right on the path, sees the goal reached, a comet crosses, catches it, finds it in the collection, and finds the lesson's constellation after mastering its last skill; verify the test passes
- [x] 6.2 Run `venv/bin/python -m pytest mathly2/tests` and `openspec validate add-rewards --strict`; verify both pass

## Workflow follow-up

- Apply the new migration after the four earlier ones (on a test project first).
- Archive this change once it is reviewed, so `rewards` moves into `openspec/specs/`; then propose `add-lesson-quizzes` in full (design and tasks).
