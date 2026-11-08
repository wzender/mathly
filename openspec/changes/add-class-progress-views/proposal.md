# Proposal

## Why

Teachers need a per-student picture of which skills and lessons each student has covered, to see at a glance where the class struggles (PRD Goal 3, TCH-7, TCH-8).

## What Changes

- A class heat map: students by skills (grouped by lesson), each cell showing the state by color and symbol.
- A lesson coverage table: students by lessons, % of skills mastered and the best quiz grade.
- Period tabs (Sep–Dec, Jan–Jun) showing states as they were at the end of the period.
- Each student's readiness for the class's upcoming test, for the teacher.
- A developer can open these views for any class.

Screens: `docs/mockups/mathly2-screens.html` (teacher tab: heat map).

## Capabilities

### New Capabilities
- `class-progress-views`: the heat map, the coverage table, period tabs and readiness per student (PRD TCH-7, TCH-8, RDY-1 for teachers).

### Modified Capabilities

## Impact

- Reads `skill-mastery`, `lesson-quizzes` and `readiness-meter` data; no new learning rules.
- Needs each skill's mastered date (already stored) to show states at the end of a period.
