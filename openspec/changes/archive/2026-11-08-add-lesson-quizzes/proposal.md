# Proposal

## Why

Each lesson needs a grade that reflects what the student knows now, and a way to improve it (PRD 4.9). Quizzes also introduce the timed, server-graded attempt and the 0–100 scale that the test stages reuse (PRD GRD-1, GRD-2).

## What Changes

- A quiz per lesson: the "boss level" node on the trail after the lesson's ring. 10 multiple-choice questions drawn from the lesson's skills, 15 minutes, server timer, feedback at the end.
- Retakes prefer new questions; the best grade is the lesson's grade.
- After a quiz: the grade, the skills where points were lost (linked to their stars), and the mistakes' names and tips, never the correct answers.
- One grade scale (0–100) and one rule for timers that end; a grades screen for the student.
- The four written quizzes authored in the bank are left for assignments (stage 6).

Screens: `docs/mockups/mathly2-screens.html` (student tab: quiz node and grades).

## Capabilities

### New Capabilities
- `lesson-quizzes`: the per-lesson quiz, its format, retakes and result (PRD QZ-1 – QZ-6).
- `grades`: the grade scale, timed attempts, and the student's grades screen (PRD GRD-1, GRD-2, STU-3).

### Modified Capabilities

## Impact

- Builds on `learning-path` (the quiz node) and the bank's questions. New `m2_` tables for attempts and grades.
- The timed-attempt engine is reused by `add-test-readiness`.
