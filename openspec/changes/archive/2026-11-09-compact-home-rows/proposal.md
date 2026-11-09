# Proposal

## Why

The rows on home repeat what every student already knows ("13 out of 15 is needed"). They should be as short as possible.

## What Changes

- **A behind lesson's row** says only the lesson, its date, a link named just "בוחן", and the best grade as a bare number, or "-" when there is none. No explanation.
- **A weak practice test's row** says only which practice test, the test's date, the link to take it again, and the best grade as a bare number. No explanation of the pass line.

## Capabilities

### Modified Capabilities
- `student-home`: "Lessons behind on home" and "Practice tests below the pass line".

## Impact

- `home.js` and its tests, PRD STU-1. No server or database change.
