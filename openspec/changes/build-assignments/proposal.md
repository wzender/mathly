# Proposal

## Why

Teachers need to give work from the material they already have and check it (see `docs/tasks/prd-mathly.md`, 4.8). Students need to hand in full written solutions.

## What Changes

- Teachers create assignments from a file, a camera photo or the drawing board.
- Students hand in their solutions, including on the drawing board.
- Teachers grade from 0 to 100 with a note, or send work back for correction.
- The drawing board is copied from the current app.

## Capabilities

### New Capabilities
- `assignments`: creating, handing in and checking assignments.
- `drawing-board`: solving on the board and handing in the board, using the board kept from the current app.

### Modified Capabilities

## Impact

- Builds on `build-foundation`. Adds assignment and submission tables and file storage in `mathly2/`. Copies `math-board.js`, `board-math.js` and `vendor/mathlive/`.
