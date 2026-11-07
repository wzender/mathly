# Spec Delta

## Purpose

Lets students write full solutions, and teachers write assignments, on the existing drawing board, and hand in the board as a picture.

## ADDED Requirements

### Requirement: Solve on the board
Wherever a question needs a written solution (open questions and assignments), the student SHALL be able to solve it on the drawing board and hand in the board as their answer.

#### Scenario: Open question
- **WHEN** a student solves an open quiz question on the board and hands it in
- **THEN** the board is saved as a picture and submitted as the answer

### Requirement: Board is kept from the current app
The drawing board, including typed math on the board and the math keyboard, SHALL be the one kept from the current app rather than rebuilt.

#### Scenario: Typed math
- **WHEN** a student types math on the board
- **THEN** the board's math keyboard is offered and the math is rendered on the board
