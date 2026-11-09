# Proposal

## Why

The practice tests below the pass line sit in a separate card, away from the test they are for. And the grades on home are bare numbers floating next to a link, so they look detached.

## What Changes

- **The practice tests below 87 move into the top card**, the nearest test's card ("המבחן הבא: 16.11 (בעוד 7 ימים)"), under its readiness and today's task. They are the nearest test's own practice tests; the other tests' are on their own cards. There is no separate card.
- **Grades are shown as a chip attached to what they belong to**: in the behind-lessons row the grade is a small chip inside the "בוחן" link ("-" when none); in a practice test's row it is a chip inside its retake button. Same text as before (a bare number or "-"), but one object with its link.

## Capabilities

### Modified Capabilities
- `student-home`: "Home shows only what is critical", "Lessons behind on home", "Practice tests below the pass line".

## Impact

- `GET /api/home` lists only the nearest test's weak practice tests; `home.js`, `app.css`; PRD STU-1. No database change.
