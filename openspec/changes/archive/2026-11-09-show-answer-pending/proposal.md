# Proposal

## Why

Tapping a choice waits for the server to grade it, and over a slow connection that takes seconds with nothing on screen changing, so the student does not know whether the tap worked and may tap again.

## What Changes

- The moment a choice is tapped it shows it is being checked: a spinner and a short line "בודקים…", the other choices are dimmed and cannot be tapped, and the choice the student tapped stays marked.
- The hint disappears when the answer arrives (right, wrong, or an error).
- It does not depend on motion: with reduced motion the words "בודקים…" are shown without the spinner turning.

## Capabilities

### New Capabilities

### Modified Capabilities
- `exercise-screen`: adds "Thinking indicator".

## Impact

- `mathly2/static/exercise.js` and `app.css`. No server change. PRD EXR-3.
