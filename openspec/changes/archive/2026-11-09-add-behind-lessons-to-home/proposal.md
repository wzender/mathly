# Proposal

## Why

A student who is behind the curriculum sees it only as a small mark on the path. Being behind is critical, so the home should say which lessons are behind and offer the two ways to catch up.

## What Changes

- **Home lists every lesson that is behind the curriculum** (its date has passed and it is not completed), the earliest date first, in a card "שיעורים בפיגור".
- **Each lesson offers two ways to finish it** (PTH-10): finish all its skills ("N מתוך M מיומנויות", opening the next unmastered skill), or pass its בוחן with at least 13 right out of 15 (opening the quiz, showing the best grade so far).
- A lesson that is completed, has no date or whose date is ahead is not listed, and with no lesson behind there is no card.

## Capabilities

### Modified Capabilities
- `student-home`: "Home shows only what is critical", and a new "Lessons behind on home".

## Impact

- `GET /api/home` gains the behind lessons (the path's lesson facts are shared, not computed twice); `home.js`; PRD STU-1. No database change.
