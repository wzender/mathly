# Proposal

## Why

Teachers need a per-student picture of which skills and lessons each student has covered (see `docs/tasks/prd-mathly.md`, 4.8).

## What Changes

- A class heat map of skill states per student, readable without relying on color.
- A lesson coverage table: % mastered and best quiz grade per student and lesson.
- Period tabs (Sep–Dec, Jan–Jun), showing states as of the end of each period.

## Capabilities

### New Capabilities
- `class-progress-views`: the heat map, lesson coverage and period tabs.

### Modified Capabilities

## Impact

- Builds on `build-skill-learning` (skill states and answer dates) and `build-lesson-quizzes` (best quiz grades).
