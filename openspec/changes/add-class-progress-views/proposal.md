# Proposal

## Why

A teacher cannot see where a class stands: which skills each student has covered, which lessons are done or behind the curriculum, and who is ready for the coming test (PRD Goal 3, TCH-7, TCH-8, RDY).

## What Changes

- A new **"התקדמות" tab** on the teacher's screen (with its number, like the other tabs) and a "התקדמות" shortcut on each class card. It shows one class at a time, with a class picker when the teacher has several.
- **Progress by lesson** (TCH-7, TCH-8): students by lessons, never by skills. Each cell is kept short: a progress bar with the percent of the lesson's skills mastered, the best quiz grade as a bare number, and a warning mark when the lesson is behind the curriculum (PTH-11). The state in words is the cell's accessible name.
- **Period tabs**: ספט׳–דצמ׳ and ינו׳–יוני. A period shows the lessons of that period (by the lesson's date in the curriculum, else the bank's month) and states as they were at the end of the period, or today for the current period.
- **Readiness** for the class's nearest coming test: each student's readiness number and word, mastery, practice average and simulation grade.
- A developer can open all of these for any class. A manager or an admin cannot: they see no learning data.

No learning rule changes. Skills never lose mastery, so a state at a past date is read from the stored started/mastered times.

## Capabilities

### New Capabilities
- `class-progress-views`: the progress by lesson, the periods and the readiness per student.

### Modified Capabilities

## Impact

- New `GET /api/classes/{id}/progress`; the counts endpoint gains the number of students; two store reads that fetch many students at once (progress and attempts), so a class costs a few database waits and not one per student; `teacher.js` and a new `teacher_progress.js`; PRD TCH-1, TCH-7, TCH-8; the permissions matrix.
- Screens: `docs/mockups/mathly2-screens.html` (teacher tab: heat map).
