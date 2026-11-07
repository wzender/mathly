# Spec Delta

## Purpose

Lets the teacher give assignments from a file, a photo or the drawing board, and check what students hand in with a grade and feedback.

## ADDED Requirements

### Requirement: Create an assignment
The teacher SHALL be able to create an assignment with a title, a note and a due date, and load its content from a file upload (PDF or images), a photo taken with the device camera, or the drawing board, where what the teacher writes is saved as the assignment's pages.

#### Scenario: From a PDF
- **WHEN** a teacher creates an assignment and uploads a PDF
- **THEN** students see the assignment with the PDF's pages

#### Scenario: From the board
- **WHEN** a teacher writes an assignment on the drawing board and saves it
- **THEN** the board is saved as the assignment's page

### Requirement: Students hand in assignments
Assignments SHALL appear in the student's "המשימות שלי", and the student SHALL be able to hand in their solution, including on the drawing board.

#### Scenario: Handing in
- **WHEN** a student solves an assignment on the board and hands it in
- **THEN** the teacher sees the submission

### Requirement: Check assignments
The teacher SHALL be able to open each student's submission and give a grade from 0 to 100 and a note, or send it back for correction.

#### Scenario: Grading
- **WHEN** a teacher gives a submission 88 with a note
- **THEN** the student sees 88 and the note, and the grade appears on their grades screen

#### Scenario: Send back
- **WHEN** a teacher sends a submission back for correction
- **THEN** the student can hand in the assignment again
