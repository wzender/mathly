# Proposal

## Why

mathly2 is slow: opening a screen makes 3 to 7 database calls and grading one practice answer makes 14, one after another, and each call to a remote Supabase takes about 0.4 seconds (measured 2026-11-08). An answer takes 5 to 6 seconds, a screen 2 to 3. mathly1 grades on the device, which mathly2 must not (the server decides), so the server has to make fewer, parallel calls.

## What Changes

- The same fact is read once per request (a student's classes were read up to 3 times, their progress 3 times per answer).
- Reads that do not depend on each other are made at the same time.
- Writes of one answer are combined (one progress write instead of two).
- The server keeps its connections to the database open and reuses them, instead of opening a new secure connection for every call.
- A requirement and a test with an artificial delay on every database call (waits in a row, not call counts), so it cannot get slow again unnoticed.

## Capabilities

### New Capabilities

### Modified Capabilities
- `app-basics`: adds "Few database round trips".

## Impact

- `mathly2/store.py` (connection reuse), `mathly2/skills.py`, `mathly2/learning.py`, `mathly2/access.py`, `mathly2/realtests.py` and `mathly2/quizzes.py` (fewer and parallel calls). No screen, route or database table changes.
- PRD 7.3 gets one line.
