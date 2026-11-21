# Proposal

## Why

The people who use the app (students, teachers, managers) see what works and what is missing first, and had no way to tell the developer.

## What Changes

- "💡" (הצעה או משוב) in the header for everyone signed in: a short sheet with the kind (an idea, a problem, other) and the text; the screen they were on goes with it. At most 20 a person a day.
- A "הצעות ומשוב" card on the developer's screen: open suggestions first with who, when and from which screen, and a button that marks one handled.
- A new server-only table `m2_feedback`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `app-basics`: suggestions and feedback.

## Impact

- `feedback.py` (new), `store.py` (four methods), `main.py`; `static/feedback.js`, `static/feedback_card.js` (new), `static/app.js`, `static/developer.js`. Migration `20261123090000_m2_feedback.sql`. PRD DEV-1.
