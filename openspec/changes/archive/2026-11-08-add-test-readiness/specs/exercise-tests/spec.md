# Spec Delta

## Purpose

Two timed, mixed practice tests per real test that train the student under test conditions and aim at their weak skills, retakeable until they are good.

## ADDED Requirements

### Requirement: Created by the app
When a teacher sets a test, the app SHALL create 2 exercise tests for every student of the class and place them on the student's countdown.

#### Scenario: New test
- **WHEN** a teacher sets a test for a class of 25
- **THEN** each of the 25 students has exercise test 1 and exercise test 2 on their countdown

### Requirement: Like the real test
An exercise test SHALL have the real test's number of questions and time limit, mix questions from all the covered lessons, hide skill names, and give feedback only at the end.

#### Scenario: During the test
- **WHEN** a student answers a question in an exercise test
- **THEN** no right or wrong is shown until the test ends

### Requirement: Question mix
Exercise test 1 SHALL draw 60% of its questions from weak skills and 40% from other covered skills; exercise test 2 SHALL draw 30% and 70%. A weak skill is one in the learning state or answered wrong in an earlier exercise test. Not-started skills MUST NOT appear; they are listed as "practice these first". Missing weak questions are filled from other covered skills.

#### Scenario: Few weak skills
- **WHEN** exercise test 1 needs 7 weak questions and the student has weak skills for only 3
- **THEN** the other 9 questions come from other covered skills

#### Scenario: Not started
- **WHEN** a covered skill is not started
- **THEN** it has no question in the test and is listed under "practice these first"

### Requirement: Retakes
The student SHALL be able to start or retake an exercise test at any time. Each retake SHALL draw new questions; the best grade counts.

#### Scenario: Retake
- **WHEN** a student retakes exercise test 2
- **THEN** it has new questions, and their best grade of the two attempts counts

### Requirement: Result links back
After an exercise test the student SHALL see their grade and the weak skills found, each linked to its star on the path. The correct answers MUST NOT be shown.

#### Scenario: Result
- **WHEN** a student finishes an exercise test with mistakes in two skills
- **THEN** the result lists those two skills with links to their stars
