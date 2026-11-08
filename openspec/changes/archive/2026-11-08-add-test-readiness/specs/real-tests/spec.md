# Spec Delta

## Purpose

Lets a teacher put a class's real school test into the app, so the app can prepare the students for it, and lets the teacher follow who has taken the required simulation.

## ADDED Requirements

### Requirement: Setting a test
The teacher of a class SHALL be able to set a test for it: a date, the lessons it covers (from the class's lessons), an optional note, the number of questions and the time limit. The number of questions SHALL default to 12 and the time limit to 45 minutes; both can be changed.

#### Scenario: Defaults
- **WHEN** a teacher sets a test without changing the number of questions or the time
- **THEN** the test has 12 questions and 45 minutes

### Requirement: Changing or removing a test
The teacher SHALL be able to change a test's date, lessons, note, length and time before its date, and remove it. Grades already earned in its exercise tests and simulation SHALL stay.

#### Scenario: Moving the date
- **WHEN** a teacher moves a test two days later
- **THEN** every student's countdown follows the new date

### Requirement: Tests tab
The teacher SHALL have a tests tab listing their classes' tests and, for each test, which students have taken the simulation and which have not.

#### Scenario: Three missing
- **WHEN** 22 of 25 students took the simulation
- **THEN** the tab shows 22 done and names the 3 who have not
