# Proposal

## Why

When a student answers wrong, the chosen choice only gets a faint salmon border and tint, which is easy to miss, and it carries no symbol or word on the choice itself, so it is shown by colour alone (the app promises never to do that).

## What Changes

- The chosen wrong choice is marked clearly: a stronger border and tint, and a label "✗ לא נכון" on the choice itself.
- Nothing else is marked: the right choice is still never shown.

## Capabilities

### New Capabilities

### Modified Capabilities
- `exercise-screen`: "A wrong answer" says the chosen choice is marked with a symbol and a word.

## Impact

- `mathly2/static/exercise.js` and `app.css`. No server change. PRD EXR-5.
