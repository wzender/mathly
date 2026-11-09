# Proposal

## Why

Using the eraser means going to the toolbar and back, and the student has to press a button to copy the question onto the board before working.

## What Changes

- **Holding the right mouse button erases**: while it is held the board erases with the current eraser size, whatever tool is chosen; letting go returns to the tool the student had. The browser's context menu does not open on the board. A pen's barrel button does the same.
- **The question appears on the board by itself**, at the top, the first time a question's sketch is shown (the exercise screen, a quiz, a practice test, the simulation). It is the same copy the "השאלה" button makes. If the student deletes it, it does not come back, and the button still places it again.

## Capabilities

### Modified Capabilities
- `smart-board`: "Tools" and "The question on the board".

## Impact

- `math-board.js` and its browser tests, PRD BRD-3 and BRD-6. No server or database change.
