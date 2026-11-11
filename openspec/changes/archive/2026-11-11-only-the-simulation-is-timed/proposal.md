# Proposal

## Why

A student doing the בוחן at the end of a lesson gets a 45-minute countdown and is handed in when it ends, and the practice tests are timed too. Only the simulation (מבחן סימולציה) should be timed: it is the one that trains for the real test's conditions.

## What Changes

- **A lesson quiz has no time limit.** It shows no timer and stays open until the student hands it in; coming back later finds it open with the answers given.
- **An exercise test (מבחן תרגול) has no time limit** either. It keeps the real test's number of questions.
- **The simulation keeps its timer** (the real test's minutes) and is still handed in as it stands when time ends.
- Attempts still store a `due_at` (the database requires one); only a simulation is held to it. Quizzes and exercise tests that were open when this shipped are no longer timed.

## Capabilities

### Modified Capabilities
- `lesson-quizzes`: "Quiz format".
- `exercise-tests`: "Like the real test".
- `grades`: "When time ends".

## Impact

- `mathly2/attempts.py` (`TIMED_KINDS`), `mathly2/quizzes.py` (`due_at` is null for an untimed attempt), `mathly2/static/quiz.js` (no timer without `due_at`), their tests, and PRD QZ-2, EXT-4, EXT-7, GRD-2. No database change.
