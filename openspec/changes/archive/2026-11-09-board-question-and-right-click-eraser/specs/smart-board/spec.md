## MODIFIED Requirements

### Requirement: Tools
The board SHALL offer: move; pen with three ink colors following pen pressure; straight line; circle dragged from its center; angle with an arc, its words and one to three arcs or a right-angle square; typed math with a ninth-grade math keyboard; eraser in three sizes; undo; and clear. Holding the right mouse button (or a pen's barrel button) SHALL erase with the current eraser size, whatever tool is chosen, and releasing it SHALL return to the chosen tool; the context menu MUST NOT open on the board.

#### Scenario: Typed math
- **WHEN** a student types a fraction with the math keyboard
- **THEN** it appears on the board as a formatted fraction that can be moved

#### Scenario: The right button erases
- **WHEN** the pen is the chosen tool and the student holds the right mouse button and drags across a stroke
- **THEN** the stroke is erased, the pen is still the chosen tool afterwards, and no context menu opened

#### Scenario: Left button as before
- **WHEN** the student then draws with the left button
- **THEN** it draws with the pen

### Requirement: The question on the board
The question (text and figures) SHALL appear at the top of the board by itself the first time a question's sketch is shown, and the "השאלה" button SHALL place a copy again. The eraser and "clear" SHALL leave it alone; it is removed by selecting and deleting it, and a deleted copy MUST NOT come back by itself.

#### Scenario: Opening the board
- **WHEN** a student opens the board on a question
- **THEN** the question's text is already at the top of the board

#### Scenario: Erasing near the question
- **WHEN** the eraser passes over the question's copy
- **THEN** the copy stays

#### Scenario: Clearing
- **WHEN** the student clears the board
- **THEN** their work goes and the question stays at the top

#### Scenario: Deleted
- **WHEN** the student deletes the question's copy and leaves and returns to the same question
- **THEN** it is not placed again by itself

#### Scenario: Another question
- **WHEN** the next question of the exercise opens
- **THEN** that question is at the top of its own board
