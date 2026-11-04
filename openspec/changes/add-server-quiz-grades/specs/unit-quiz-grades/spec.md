# Spec Delta

## Purpose

Makes the server the only source of a student's unit-quiz grade, so the grade the student and the class teacher see cannot be changed from the student's device.

## ADDED Requirements

### Requirement: Submitting a unit quiz records a sitting on the server
When a signed-in student submits a unit quiz, the system SHALL store a sitting with the unit, the quiz's attempts in question order, the submission time and whether the time ran out. Every attempt in the sitting MUST belong to the submitting student and to that unit's quiz questions.

#### Scenario: Student submits a quiz
- **WHEN** a signed-in student submits the unit quiz of unit `t` with one attempt for each of its four questions
- **THEN** the server stores a sitting for that student and unit with the four attempts in question order, and returns its id

#### Scenario: Attempt of another student is rejected
- **WHEN** a submission names an attempt that belongs to another account
- **THEN** the server rejects the submission and stores no sitting

#### Scenario: Attempt of another question is rejected
- **WHEN** a submission for unit `t` names an attempt whose question is not one of unit `t`'s quiz questions, or puts an attempt in the wrong question position
- **THEN** the server rejects the submission and stores no sitting

#### Scenario: Repeated submit
- **WHEN** the same sitting is submitted twice (for example after a lost response)
- **THEN** the server keeps one sitting and returns the same id both times

### Requirement: The server computes a sitting's grade from the stored checks
A sitting's grade SHALL be the sum over its questions of the question's points multiplied by its completed check's score out of 100, rounded per question. A question without a saved photo SHALL earn 0. The grade SHALL be absent while any question with a photo has no completed check with a score.

#### Scenario: All answers checked
- **WHEN** every question of a sitting has a completed check with a score
- **THEN** the sitting's grade is the weighted sum, out of 100

#### Scenario: One answer still waiting
- **WHEN** one question has a photo whose check is still waiting for the teacher, still running, or ended without a score (unreadable or needs review)
- **THEN** the sitting has no grade and reports how many questions are still open

#### Scenario: Missing photo
- **WHEN** a question in a sitting has no saved photo
- **THEN** that question earns 0 points and does not keep the grade open

### Requirement: Student sees the server's grade
The unit-quiz result screen SHALL show the grade the server computed for the sitting. A grade written by the device into its progress MUST NOT be shown in its place.

#### Scenario: Result screen
- **WHEN** a student opens the result of a submitted sitting whose answers are all checked
- **THEN** the screen shows the grade returned by the server

### Requirement: Class report shows only server grades for unit quizzes
The class report SHALL take each student's unit-quiz grades, submission counts and dates only from the server's sittings. Values in the student's uploaded progress MUST NOT change what the report shows for unit quizzes.

#### Scenario: Edited progress object
- **WHEN** a student's uploaded progress claims a unit-quiz score of 100 but the server's sitting for that unit has a grade of 62
- **THEN** the class report shows 62

#### Scenario: Sitting in progress
- **WHEN** a student's latest sitting for a unit still has unchecked answers
- **THEN** the report shows that unit's quiz as waiting for checking, without a grade

#### Scenario: Old sitting without a server record
- **WHEN** a student's progress lists a unit-quiz submission from before this change and the server has no sitting for it
- **THEN** the report lists it as not verified and shows no grade for it

### Requirement: Report labels device-reported numbers
The class report SHALL label skill progress, gold stars and practice-exam results as reported by the student's device, so they are told apart from server-checked unit-quiz grades.

#### Scenario: Teacher opens a student's card
- **WHEN** the teacher opens a student's card in the class report
- **THEN** the skills and practice-exam sections carry a label saying they come from the student's practice device, and the unit-quiz section does not
