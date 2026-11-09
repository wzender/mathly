# lesson-quizzes Specification

## Purpose
A retakeable quiz for every lesson that gives the lesson its grade and points the student back to the skills that lost points.

## Requirements

### Requirement: A quiz per lesson
Every lesson SHALL have one quiz, shown as a node on the trail after the lesson's ring and always open. The student SHALL be able to retake it at any time; the best grade SHALL be the lesson's grade.

#### Scenario: Better retake
- **WHEN** a student scores 60 and then 85 on a lesson's quiz
- **THEN** the lesson's grade is 85

#### Scenario: Worse retake
- **WHEN** a student scores 85 and then 70
- **THEN** the lesson's grade stays 85

### Requirement: Quiz format
A quiz SHALL be 15 multiple-choice questions drawn from the bank questions of the lesson's skills, at least one per skill and the rest spread evenly, in 45 minutes (3 minutes for each question). Skill names MUST NOT be shown, and there SHALL be no feedback until the end. The board and calculator SHALL be available.

#### Scenario: Lesson with four skills
- **WHEN** a quiz is drawn for a lesson with four skills
- **THEN** it has 15 questions and every skill has at least three

#### Scenario: The time
- **WHEN** a student starts a quiz
- **THEN** its timer shows 45 minutes

### Requirement: Retakes draw new questions
Each retake SHALL prefer questions the student has not had in earlier attempts at this quiz, the least-used first.

#### Scenario: Second attempt
- **WHEN** a student retakes a quiz
- **THEN** none of its questions were in the first attempt, as long as the lesson has enough unused questions

### Requirement: After a quiz
After a quiz the student SHALL see the grade, the skills where points were lost (each linked to its star) and, for each missed question, the name and tip of the mistake. The correct answers MUST NOT be shown.

#### Scenario: Two misses
- **WHEN** a student misses two questions of one skill
- **THEN** the result lists that skill with a link and shows the two mistakes' names and tips, without the right answers

### Requirement: Written quizzes are not lesson quizzes
The written quizzes authored in the bank SHALL NOT be used as lesson quizzes; they are offered to teachers as assignments.

#### Scenario: Lesson with an authored written quiz
- **WHEN** a student opens the quiz of a lesson that has an authored written quiz in the bank
- **THEN** the quiz is the 10-question multiple-choice quiz

### Requirement: Passing a quiz
A quiz SHALL be passed when its grade is at least 87, which is 13 right answers out of 15. A lesson whose quiz was passed at least once SHALL stay passed whatever later retakes score.

#### Scenario: Thirteen of fifteen
- **WHEN** a student gets 13 of 15 right
- **THEN** the quiz is passed

#### Scenario: Twelve of fifteen
- **WHEN** a student gets 12 of 15 right
- **THEN** the quiz is not passed (grade 80)

#### Scenario: A worse retake
- **WHEN** a student passed once and then scores 60
- **THEN** the lesson is still passed
