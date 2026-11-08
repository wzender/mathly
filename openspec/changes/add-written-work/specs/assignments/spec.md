# Spec Delta

## Purpose

Lets a teacher give work from any material to a class, and check what students hand in, from one inbox.

## ADDED Requirements

### Requirement: Giving an assignment
A teacher SHALL create an assignment for a class they teach, with a title, a note and a due date, and its pages from: a file from the computer (PDF or images), a photo from the device camera, the board, or one of the written quizzes authored in the bank.

#### Scenario: From the board
- **WHEN** a teacher writes an assignment on the board and saves it
- **THEN** the board's pages become the assignment's pages

#### Scenario: From the bank
- **WHEN** a teacher picks the bank's written quiz of "טכניקה אלגברית 1"
- **THEN** its four questions become the assignment, with their points

### Requirement: An exercise test as an assignment
A teacher SHALL be able to send one of their real test's two exercise tests to the whole class as an assignment with a due date. Students SHALL see it under "המשימות שלי"; it opens the exercise test, counts as done when the student has taken it, and its grade is the exercise test's best grade. It is not handed in as a picture and does not wait in the inbox.

#### Scenario: Sent to the class
- **WHEN** a teacher sends exercise test 1 of a test to the class with a due date
- **THEN** every student sees it in "המשימות שלי", and it opens the exercise test

#### Scenario: Not in the inbox
- **WHEN** a student finishes the exercise test
- **THEN** the assignment shows as done with the test's grade, and nothing is added to the teacher's inbox

### Requirement: My assignments
A student SHALL see their assignments on home under "המשימות שלי" with the due date and state, open one, work on it on the board or on paper, and hand it in.

#### Scenario: Hand-in
- **WHEN** a student hands in an assignment from the board
- **THEN** it shows as handed in, and the teacher's inbox lists it

### Requirement: Teacher inbox
A teacher SHALL have one inbox of everything their students handed in that waits for them, oldest first: submissions not checked yet and requests to look again. A submission sent back waits for the student, not in the inbox.

#### Scenario: Oldest first
- **WHEN** two students hand in on Monday and Tuesday
- **THEN** Monday's submission is first in the inbox

### Requirement: Checking a submission
The teacher SHALL open a submission, give a grade from 0 to 100 and a note, or send it back for correction with a note. The student SHALL see the grade and note, or the request to correct.

#### Scenario: Sent back
- **WHEN** a teacher sends a submission back with "חסר נימוק בסעיף 2"
- **THEN** the student sees the note and can hand in again
