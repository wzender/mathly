# Proposal

## Why

Each lesson needs a grade that reflects what the student knows now, and a way to improve it (see `docs/tasks/prd-mathly.md`, 4.2).

## What Changes

- One retakeable quiz (בוחן) per lesson. Each retake draws new questions, and the best grade is the lesson's grade.
- After a quiz, the skills where points were lost are listed.
- Grades are computed and stored on the server.
- Quizzes are added to the bank for the 20 lessons that lack one.

## Capabilities

### New Capabilities
- `lesson-quizzes`: the quiz per lesson, retakes, best grade, and skills to practise.

### Modified Capabilities

## Impact

- Builds on `build-foundation` and `build-skill-learning` (skill states and the path). Adds quiz attempt tables in `mathly2/`.
