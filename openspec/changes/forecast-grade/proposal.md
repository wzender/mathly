# Proposal

## Why

The readiness number moves only with tests and deepening, and says how far along the student is, not what they would get. Students want
to see the grade they are heading for, and a bar that fills with every activity in the game.

## What Changes

- A forecast grade per upcoming test: a chance per skill of the test from its state and the latest answers on it (the newest weigh most, test answers double), averaged over the test's skills, with a range that narrows with practice.
- Home's test strip shows it as a game in place of the readiness number (which stays on the test's page): "finding your league" until 15 answers on the test's material (no low first guess is ever shown), then a league (🌙 ירח, 🪐 כוכב לכת, ⭐ כוכב, 🌌 גלקסיה) with the points to the next one, cheered when revealed or moving up, held through a small dip. The grade counts up with "+N"; a drop is shown quietly.
- The result of a lesson round shows the forecast; the test's page shows it above readiness; the teacher's tests tab has a column for it.
- One new read: the student's latest answers on every skill (`recent_answers`); a route `/api/forecast` for the nearest test.

## Capabilities

### New Capabilities

### Modified Capabilities
- `readiness-meter`: the forecast grade.

## Impact

- `forecast.py` (new), `realtests.py`, `store.py` (`recent_answers`), `reads.py`; `static/home.js`, `static/round.js`, `static/testcard.js`, `static/teacher.js`. PRD RDY-6.
