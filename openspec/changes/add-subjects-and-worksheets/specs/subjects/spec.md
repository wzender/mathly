# Spec Delta

## Purpose

Defines what a subject is, who creates and renames it, which classes study it, and how its lessons are ordered and published, so the app can teach more than one subject.

## ADDED Requirements

### Requirement: A subject and its lessons
A subject SHALL have a name (1–60 characters, unique ignoring case), an icon chosen from a fixed set, and an ordered list of lessons. Math SHALL be a subject from the start, holding every lesson of the math content file in the file's order, and SHALL keep its current name.

#### Scenario: Math from the start
- **WHEN** the app starts with no subject created yet
- **THEN** there is one subject, math, with every lesson of the math content file in that file's order

#### Scenario: A duplicate name
- **WHEN** a manager creates a subject named "מדעים" while "מדעים" exists
- **THEN** it is refused with a message that the name is taken

### Requirement: Who creates and renames subjects
A manager or a developer SHALL be able to create a subject and change its name and icon. Nobody else SHALL be able to. Math MUST NOT be renamed or deleted. A subject with published lessons MUST NOT be deleted; a subject with no published lesson MAY be deleted, and its drafts with it.

#### Scenario: A manager creates a subject
- **WHEN** a manager creates the subject "מדעים" with an icon
- **THEN** it appears in the subjects list with no lessons

#### Scenario: A teacher cannot
- **WHEN** a teacher asks the server to create a subject
- **THEN** the server refuses with 403

#### Scenario: Math is fixed
- **WHEN** a manager renames or deletes math
- **THEN** it is refused, and math keeps its name and its lessons

#### Scenario: Deleting a subject with lessons
- **WHEN** a manager deletes a subject that has a published lesson
- **THEN** it is refused, and the message says to unpublish its lessons first

### Requirement: Ordering a subject's lessons
A manager or a developer SHALL be able to change the order of a subject's lessons from the database. The math content file's lessons SHALL keep their order and SHALL come before any lesson added to math in the database.

#### Scenario: Moving a lesson
- **WHEN** a manager moves the second lesson of "מדעים" to be first
- **THEN** the path of every student studying "מדעים" shows it first

### Requirement: A class studies chosen subjects
A class SHALL have a list of subjects it studies; a new class SHALL study math only. A manager or a developer SHALL choose a class's subjects in the class editor. A class SHALL study every published lesson of each of its subjects.

#### Scenario: A new class
- **WHEN** a manager creates a class without choosing subjects
- **THEN** the class studies math only

#### Scenario: Adding a subject to a class
- **WHEN** a manager adds "מדעים" to class ט'3
- **THEN** the students of ט'3 have every published lesson of "מדעים" as well as math

#### Scenario: Removing a subject from a class
- **WHEN** a manager removes "מדעים" from class ט'3
- **THEN** its lessons leave those students' paths, and their progress in them is kept

### Requirement: Only published lessons reach students
A lesson SHALL be a draft until it is published. A draft MUST NOT appear on any path, quiz, test, grade or review list, and the server MUST NOT serve its questions to a student.

#### Scenario: A draft
- **WHEN** a manager has a draft lesson in "מדעים" and a student of a class studying "מדעים" opens the path
- **THEN** the draft lesson is not there

### Requirement: Progress is kept
Unpublishing a lesson, removing a subject from a class or moving a lesson MUST NOT delete any student's answers, mastery, quiz grades or test grades. A lesson published again SHALL show the progress it had.

#### Scenario: Published again
- **WHEN** a lesson a student mastered two skills in is unpublished and then published again
- **THEN** the student's path shows those two skills mastered
