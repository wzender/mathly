# Spec Delta

## Purpose

Defines the student's main screens: home with assignments, the test reminder and a way back to the path, and a grades screen with every grade that counts.

## ADDED Requirements

### Requirement: Student home
The student's home SHALL show their assignments from the teacher ("המשימות שלי"), the reminder for the nearest test (days left, readiness meter and today's task), and a way to continue the path.

#### Scenario: Assignment and test
- **WHEN** a student has an open assignment and a test in 6 days
- **THEN** home shows the assignment, the test reminder with today's task, and continue the path

#### Scenario: Nothing scheduled
- **WHEN** a student has no assignments and no upcoming test
- **THEN** home still offers to continue the path

### Requirement: Grades screen
The student SHALL have a grades screen listing every lesson quiz (best grade), every exercise test (best grade), every simulation grade and every assignment grade.

#### Scenario: Quiz retaken
- **WHEN** a student got 70 and then 90 on a lesson's quiz
- **THEN** the grades screen shows 90 for that quiz

### Requirement: No student-to-student features
The app MUST NOT offer student-to-student features such as chat or leaderboards, and MUST NOT show a student other students' results.

#### Scenario: Grades screen
- **WHEN** a student opens their grades
- **THEN** no other student's grade or rank is shown
