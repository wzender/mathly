# Proposal

## Why

Students often finish a topic without mastering it (see `docs/tasks/prd-mathly.md`). The path teaches each skill step by step and proves mastery instead of assuming it.

## What Changes

- Each skill teaches in four stages: a worked example with "why this step?", faded examples, practice, and feedback that names the mistake and gives a similar question.
- Mastery: 3 correct in a row, first try, no help, over 2 calendar days, checked on the server. Mastery never decays.
- A path screen with every lesson open, a daily goal and streak, and a collection screen.
- Worked examples, faded examples and "why this step?" choices are added to the bank, skill by skill. A stage with no content is skipped, so every skill works through practice from day one.

UI sketch: [static mockup](./mockups/skill-learning.html) (path, worked example, faded example, practice, collection).

## Capabilities

### New Capabilities
- `skill-learning`: the four stages of learning a skill.
- `skill-mastery`: the mastery rule and skill states.
- `learning-path`: lessons open in any order, the path screen, daily goal and streak, collection.

### Modified Capabilities

## Impact

- Builds on `build-foundation`. Adds answer storage (`m2_` tables) and student screens in `mathly2/`.
