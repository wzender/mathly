# Proposal

## Why

A student who masters the test's material in deepening is more ready, but the readiness number ignored it: only tests moved it. The teacher
wants deepening to count too, while tests stay the main way up.

## What Changes

- The share of the test's skills mastered sets where the number starts: it closes 20% of the gap from 0 (all of the material mastered starts it at 20).
- Tests then pull it up as before (a practice test 30% of the gap, a simulation 60%, a manual one 15%), and a lower grade never lowers it.
- Mastering more skills after the tests still raises the number.
- The test's page explains it, with what deepening gives now.

## Capabilities

### New Capabilities

### Modified Capabilities
- `readiness-meter`: deepening counts as the starting point.

## Impact

- `readiness.py` (the start and its share), `realtests.py` (the share of the test's skills mastered), `static/testcard.js` (the explanation). PRD RDY-2, RDY-4.
