# smart-board Specification

## Purpose
A drawing board for working out and handing in a full solution with pen, shapes, typed math and a calculator, beside the question on a computer and over it on a phone.

## Requirements

### Requirement: Opening the board
The board SHALL open from a button in the header of the exercise screen and of every other screen that offers it. On a computer it SHALL sit beside the exercise and the device SHALL remember whether it is on; on a phone or tablet it SHALL open full screen over the exercise and close back to the question.

#### Scenario: Phone
- **WHEN** a student presses the board button on a phone
- **THEN** the board covers the screen, and closing it shows the same question

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

### Requirement: Everything is an object
Every stroke, line, circle, angle and formula SHALL be selectable, movable and erasable. Line ends and circle centers SHALL snap to existing ends and centers, and lines joined that way SHALL move together.

#### Scenario: Closing a triangle
- **WHEN** a student draws three lines whose ends meet
- **THEN** the ends snap together and moving one corner moves both lines

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

### Requirement: Endless paper with palm rejection
The paper SHALL grow downward and to the right and scroll with the wheel, two fingers, or dragging empty paper. Once a pen has touched the screen a single finger SHALL be ignored, and while the pen writes every touch and any wide contact SHALL be ignored.

#### Scenario: Resting palm
- **WHEN** a student writes with a pen while their palm rests on the screen
- **THEN** only the pen draws

### Requirement: Sketches stay on the device
Each question SHALL keep its own sketch while the page is open, and nothing SHALL be sent anywhere unless the student hands it in.

#### Scenario: Switching questions
- **WHEN** a student draws on question 1, moves to question 2 and back
- **THEN** question 1's sketch is still there, and nothing was sent

### Requirement: Handing in a sketch
Where a screen accepts a written answer, the board SHALL turn the sketch into a picture that the student hands in from the board.

#### Scenario: Hand-in
- **WHEN** a student presses the board's hand-in button on such a screen
- **THEN** a picture of the sketch is handed in

### Requirement: Calculator
A scientific calculator in the layout of a Casio fx-991ES PLUS, with SHIFT functions, SHALL open on a panel over a corner of the paper from a toolbar button, wherever the board is.

#### Scenario: Sine
- **WHEN** a student opens the calculator and computes sin 30 in degrees
- **THEN** it shows 0.5

### Requirement: Labels and input
Every tool SHALL have a Hebrew label and an icon, and the board SHALL work with touch, pen and mouse.

#### Scenario: Screen reader
- **WHEN** a screen reader reaches the pen tool
- **THEN** it reads its Hebrew name
