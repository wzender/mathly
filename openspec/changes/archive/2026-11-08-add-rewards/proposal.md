# Proposal

## Why

Practice works after stage 2, but nothing pulls a student back tomorrow. mathly1's game layer does: a daily goal and streak, stars that fade when neglected, a collection of stars and constellations, and rare comets to catch (PRD MST-6 – MST-8, CMT-1 – CMT-4).

## What Changes

- A daily goal of 5 correct answers and a streak, shown at the top of the path.
- Fading stars: a mastered skill not practiced for 14 days dims and says "דועך"; one answer relights it. Only a cue: the skill stays mastered.
- A collection screen: mastered skills as stars, completed lessons as constellations, caught comets with their facts.
- Twelve comets that may cross the exercise screen after a right answer; the first comes with the first daily goal reached.

Screens: `docs/mockups/mathly2-screens.html` (student tab: path top, collection).

## Capabilities

### New Capabilities
- `rewards`: the daily goal and streak, fading stars, the collection and comets.

### Modified Capabilities

## Impact

- Builds on `skill-mastery`, `learning-path` and `exercise-screen` (stage 2). Reuses today's daily-goal and streak rules.
- Stores caught comets per student (an `m2_` table).
- Ports the constellation and comet drawings from mathly1's `static/math-sky.js`.
