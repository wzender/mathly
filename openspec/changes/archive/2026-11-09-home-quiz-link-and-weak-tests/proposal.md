# Proposal

## Why

The "שיעורים בפיגור" card on home is heavier than it needs to be, and the home does not show the practice tests the student did badly on.

## What Changes

- **The behind-lessons card is shorter**: each lesson shows its name, the date and one link, to its בוחן (with the best grade so far and the 13 of 15 needed). The "finish the skills" option is removed.
- **Home also lists the practice tests (מבחני תרגול) that did not reach 13 right out of 15**, a grade of 87: for each upcoming test, every practice test that was taken and whose best grade is below 87, with the grade and a link to try again. A practice test not taken yet, or already at 87 or more, is not listed (a test not taken is already today's task and is on the test's card).

## Capabilities

### Modified Capabilities
- `student-home`: "Home shows only what is critical", "Lessons behind on home"; "Two ways to catch up" is removed; "Practice tests below the pass line" is new.

## Impact

- `GET /api/home`: the behind lessons lose the skills fields, and a list of weak practice tests is added; `home.js`; PRD STU-1. No database change.
