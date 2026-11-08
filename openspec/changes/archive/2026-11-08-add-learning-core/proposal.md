# Proposal

## Why

After the foundation, students can sign in but cannot learn. This stage is the smallest product a class can use: mathly1's path of stars, its exercise screen with instant feedback, its smart board, and mastery proven over two days (PRD 4.4–4.7).

## What Changes

- The exercise screen from mathly1: one question at a time, choices in a new order each time, instant server grading, quiet wrong answers that name the mistake without revealing the answer, a different next question, a "?" help with the explanation and a solved example, related-skill chips.
- The subject choice from mathly1: after sign-in a card per subject (math only) with a progress bar, leading to the path.
- The path from mathly1: lesson hubs with numbered rings of stars on a trail, the owl on the next skill, every lesson open.
- The smart board kept as files from mathly1, opened beside or over the exercise.
- Mastery: 3 correct in a row, first try, no help, on 2 days; never decays.
- **BREAKING** (for the current `mathly2` code): the worked-example and faded-example stages are removed.

Screens: `docs/mockups/mathly2-screens.html` (student tab: path and exercise).

## Capabilities

### New Capabilities
- `skill-mastery`: skill states, the mastery rule, help that does not count, server-dated answers (PRD MST-1 – MST-5).
- `exercise-screen`: practicing one skill (PRD EXR-1 – EXR-10).
- `learning-path`: the trail of lesson hubs and stars, the next skill, all lessons open (PRD PTH-1 – PTH-9 without the quiz node and the daily goal).
- `smart-board`: the drawing board, its tools and handing in a sketch (PRD BRD-1 – BRD-12).

### Modified Capabilities

## Impact

- Reuses from today's `mathly2`: answers and progress tables, `learning.py` (mastery, next question), question keys, figures, the practice API.
- Removes: the worked/faded example stages, their bank checks and screens, and the old list-style path.
- Copies `static/math-board.js`, `static/board-math.js` and `static/vendor/mathlive/` from mathly1 unchanged.
