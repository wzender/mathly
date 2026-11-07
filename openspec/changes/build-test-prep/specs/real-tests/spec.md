# Spec Delta

## Purpose

Lets the teacher put a real school test (מבחן) in the app, with its date, covered lessons, number of questions and time limit, so the app can prepare students for it.

## ADDED Requirements

### Requirement: Teacher sets a test
The teacher SHALL be able to set a test with a date, the lessons it covers, an optional note, the number of questions and the time limit. The number of questions SHALL default to 12 and the time limit to 90 minutes, and the teacher SHALL be able to change both.

#### Scenario: Defaults
- **WHEN** a teacher sets a test without changing the question count or time limit
- **THEN** the test has 12 questions and 90 minutes

#### Scenario: Custom limits
- **WHEN** a teacher sets a test with 10 questions and 45 minutes
- **THEN** the test is saved with 10 questions and 45 minutes

### Requirement: Tests tab
The teacher SHALL have a tests tab to set tests and see, for each test, which students have taken its simulation test and which have not.

#### Scenario: Simulation status
- **WHEN** a teacher opens a test in the tests tab and 20 of 25 students took the simulation
- **THEN** the 20 are shown as taken and the 5 as not taken

### Requirement: Real test grades are not handled
The app MUST NOT grade the real school test or import its grades.

#### Scenario: After the test date
- **WHEN** a test's date has passed
- **THEN** the app offers no way to enter or import grades for it
