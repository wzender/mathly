# Proposal

## Why

Practice on a skill should be a clear task: answer its 10 questions, each once, and see how it went. Today questions come round again by "least seen", a wrong answer is queued to return, and the counter ("question n of 10") counts only right answers, so with a wrong answer it never reaches 10 and practice never ends.

## What Changes

- Practising a skill is a **round** of its 10 questions (all of them when it has fewer), each shown once in a random order. A wrong answer is wrong: the question does not come back in the round.
- After the 10th answer the sheet shows the round's result ("N מתוך 10") with the mistakes' names and tips, and offers "סבב חדש" (a new round, the questions again in a new order) and a way back to the path.
- The counter and the dots show how far the student is in the round: a dot per question, filled for a right answer and marked for a wrong one.
- Mastery does not change (3 right in a row on the first try, on 2 days), and is counted across rounds.
- The round is remembered on the server: leaving and coming back continues it, and a finished round shows its result again.

## Capabilities

### New Capabilities

### Modified Capabilities
- `exercise-screen`: "One question at a time", "A right answer", "A wrong answer" and "A different next question" change; a round's result and a new round are added.

## Impact

- A migration adds `round_start` to `m2_skill_progress` (one column, nothing else changes); `mathly2/learning.py`, `mathly2/skills.py`, `mathly2/store.py`, `mathly2/static/exercise.js`. PRD EXR-2, EXR-4 to EXR-6 and a new EXR-12.
