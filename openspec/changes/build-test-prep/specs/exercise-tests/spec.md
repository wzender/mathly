# Spec Delta

## Purpose

Gives each student two retakeable, timed, mixed exercise tests (מבחן תרגול) before a real test, weighted toward their weak skills, so the real test does not surprise them.

## ADDED Requirements

### Requirement: Two exercise tests per test
When the teacher sets a test, the system SHALL create 2 exercise tests for every student in the class and place them on the student's countdown.

#### Scenario: Test set
- **WHEN** a teacher sets a test for a class of 25
- **THEN** each of the 25 students has exercise test 1 and exercise test 2 on their countdown

### Requirement: Teacher can assign an exercise test
The teacher SHALL be able to send an exercise test to the whole class as an assignment.

#### Scenario: Assigning
- **WHEN** a teacher sends exercise test 1 to the class
- **THEN** every student in the class sees it among their assignments

### Requirement: Retakes and best grade
The student SHALL be able to start or retake an exercise test at any time. Each retake SHALL draw new questions, and the best grade SHALL count.

#### Scenario: Retake
- **WHEN** a student got 60 and then 75 on exercise test 1
- **THEN** exercise test 1's grade is 75, and the second attempt had new questions

### Requirement: Built like the real test
An exercise test SHALL have the real test's number of questions and time limit, mix questions from all covered lessons, not show skill names, and give feedback only at the end.

#### Scenario: Taking the test
- **WHEN** a student takes an exercise test for a test of 12 questions and 90 minutes
- **THEN** it has 12 questions from the covered lessons, a 90-minute limit, no skill names, and no feedback until handed in

### Requirement: Question mix by weak skills
Exercise test 1 SHALL draw 60% of its questions from weak skills and 40% from other covered skills; exercise test 2, 30% and 70%. A weak skill is one in the "learning" state or answered wrongly in a previous exercise test. With too few weak skills, the rest SHALL come from other covered skills.

#### Scenario: Test 1 mix
- **WHEN** a student with enough weak skills opens exercise test 1 of 10 questions
- **THEN** 6 questions are on weak skills and 4 on other covered skills

#### Scenario: Few weak skills
- **WHEN** a student has only enough weak-skill questions for 2 of the 6 weak slots
- **THEN** the other slots are filled from other covered skills

### Requirement: Skills not started are left out
Skills in the "not started" state MUST NOT appear in an exercise test. The exercise test card SHALL list them as "practice these first".

#### Scenario: Not started skill
- **WHEN** a covered skill is "not started" for the student
- **THEN** no question on it appears, and the card lists it under "practice these first"

### Requirement: Result links back to the path
After an exercise test, the system SHALL show the weak skills it found and link each to its place in the path. The grade SHALL be computed and stored on the server.

#### Scenario: Result
- **WHEN** a student hands in an exercise test with mistakes on 3 skills
- **THEN** the result lists those skills, each opening its place in the path
