# Proposal

## Why

A student sees a number ("4, מתחילים") and does not know how it is made, or why it cannot pass 80.

## What Changes

- **An info button "ⓘ" beside the readiness number** opens a short tooltip that explains it in three lines: what the three parts are and their weights, that a missing part is left out, and that without the simulation it cannot pass 80. It opens on hover, on focus and on tap, and closes on a second tap, a tap elsewhere or Escape.
- It is on every place the readiness bar is shown (home and the test's card).

## Capabilities

### Modified Capabilities
- `readiness-meter`: "The number explains itself".

## Impact

- `home.js` (the bar), `app.css`; PRD RDY-4. No server or database change.
