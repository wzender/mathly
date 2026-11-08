# Proposal

## Why

Students arrive at the real test without having practised mixed, timed questions or knowing their gaps (PRD Goal 2). This stage turns a test the teacher sets into a plan the student follows day by day, with two exercise tests, one required simulation and a readiness meter (PRD 4.10–4.13).

## What Changes

- The teacher sets a real test: date, lessons, number of questions and time limit (default 12 and 45 minutes), and sees who took the simulation.
- The countdown plan from the PRD's table, shortened evenly when the test is less than 9 days away.
- Two exercise tests per student, created automatically, weighted toward weak skills (60/40, then 30/70), retakeable.
- One required simulation, like the real test, open from ~5 days before until the test day, one attempt.
- The readiness meter: one 0–100 number from mastery, exercise tests and the simulation, capped at 80 until the simulation.
- The student's home: the nearest test, its readiness and one task for today, and a button that continues the path. The subject card now opens home (as in mathly1) instead of the path, and the tab bar (home, path, grades, collection) moves to the bottom of the screen.

Screens: `docs/mockups/mathly2-screens.html` (student tab: home; teacher tab: tests).

## Capabilities

### New Capabilities
- `real-tests`: setting a test and the teacher's tests tab (PRD TST-1, TCH-6).
- `test-countdown`: the day-by-day plan (PRD TST-2).
- `exercise-tests`: the two weighted, retakeable practice tests (PRD EXT-1 – EXT-7).
- `simulation-test`: the one required full simulation (PRD SIM-1 – SIM-5).
- `readiness-meter`: the readiness number and its parts (PRD RDY-1 – RDY-3).
- `student-home`: the student's home with today's task (PRD STU-1, TST-3).

### Modified Capabilities
- `learning-path`: "Choosing a subject": the card opens the subject's home instead of the path.

## Impact

- Reuses the timed-attempt engine and grade scale from `add-lesson-quizzes`, and skill states from `skill-mastery`.
- New `m2_` tables for tests, exercise tests and simulations.
