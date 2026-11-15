# Proposal

## Why

A real exam has no choices: the student writes the solution and the checker gives points for the way. A multiple-choice simulation lets a
student guess and does not practise writing a full solution, so it says little about the real test.

## What Changes

- The simulation has no choices. Each question is answered on its board; when the right answer is a plain number (5, x = 5, 70°, 1/4), a box takes the final answer too.
- After the hand-in the simulation is "בבדיקה". The AI checks each board (with the question, the right answer for it only, and the typed answer) and gives full, half or no points; a question with an empty board is 0. The grade, the readiness gain, the review list and the mistakes round come only once it is checked.
- The teacher's points for a question replace the AI's, and the teacher's check is final. Without the AI (no key, or a failed check), the simulation waits for the teacher.
- Lesson quizzes and practice tests stay multiple-choice.

## Capabilities

### New Capabilities

### Modified Capabilities
- `simulation-test`: written answers, the AI's check as the grade, and waiting for the check.

## Impact

- `writtentest.py` (new), `attempts.py`, `quizzes.py`, `boardreview.py`, `boardwork.py`, `realtests.py`, `rounds.py`; `static/quiz.js`, `static/teacher_boardwork.js`.
- No migration: a written simulation keeps the typed answers in `answers` and has no `grade` until it is checked.
