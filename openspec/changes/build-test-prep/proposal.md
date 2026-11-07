# Proposal

## Why

Students arrive at the real test without having practised mixed, timed questions or knowing their gaps (see `docs/tasks/prd-mathly.md`, 4.3–4.7).

## What Changes

- The teacher sets a real test (date, lessons, number of questions, time limit) and sees who took the simulation.
- The student gets a countdown plan, two retakeable exercise tests weighted toward weak skills, and one required simulation with a timer kept on the server.
- A readiness meter for the student and the teacher.
- The student's home (assignments, test reminder with today's task, continue the path) and the grades screen.

## Capabilities

### New Capabilities
- `real-tests`: setting a test and the tests tab.
- `test-countdown`: the plan by days left and today's task.
- `exercise-tests`: two exercise tests with a weak-skill question mix.
- `simulation-test`: the one-time simulation with a window and a server timer.
- `readiness-meter`: readiness per upcoming test.
- `student-screens`: the student's home and grades screen.

### Modified Capabilities

## Impact

- Builds on `build-foundation`, `build-skill-learning`, `build-lesson-quizzes` and `build-assignments` (home and grades show their items).
