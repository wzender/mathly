# Proposal

## Why

Students have short gaps (a bus, a queue) with only a phone. Most practice needs a board; a round of questions answered in the head turns
those minutes into practice.

## What Changes

- The bank's questions that need no board are classified once into `content/onthego.json`: a student who knows the topic picks the answer in their head within about 30 seconds (a definition, a property, which statement is true, reading a figure or graph, one simple step). 755 of 1,050.
- "🚌 תרגול בנסיעה" on home starts a round of 10 such questions with no board button, at most 2 a skill, unmastered skills and the nearest test's lessons first. Answers are practice answers. It ends with the score and "עוד סבב בנסיעה".
- A migration adds the attempt kinds `onthego_round` and `mistakes_round`; the mistakes round was refused by the database before.

## Capabilities

### New Capabilities

### Modified Capabilities
- `student-home`: practice on the go.

## Impact

- `onthego.py` and `content/onthego.json` (new), `rounds.py` (the start route and the round's view), `realtests.home` (`onthego`), `main.py`; `static/round.js`, `static/student.js`, `static/home.js`. Migration `20261122090000_m2_round_kinds.sql`. PRD STU-1.
