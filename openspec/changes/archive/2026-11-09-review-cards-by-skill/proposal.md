# Proposal

## Why

The חזרה tab shows one question at a time, so the student cannot see how much there is to review or which skills it is about.

## What Changes

- **חזרה shows every waiting question as a card**, all on the page, **grouped by skill**: a heading per skill (with its lesson and how many cards it holds), and under it that skill's questions, the oldest first.
- Each card is answered in place. A right answer marks the card done and removes it from the list; a wrong answer keeps it, names the mistake and its tip, and offers "נסו שוב".
- The skills come in the bank's order. A skill with no waiting question has no heading.

## Capabilities

### Modified Capabilities
- `review`: "The חזרה tab" and "Redoing a question".

## Impact

- `GET /api/review` returns the groups instead of one question; `POST /api/review/answer` no longer picks a next question. `review.js`, the PRD STU-8 and the review tests change. No database change.
