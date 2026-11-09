## MODIFIED Requirements

### Requirement: Quiz format
A quiz SHALL be 15 multiple-choice questions drawn from the bank questions of the lesson's skills, at least one per skill and the rest spread evenly, in 20 minutes. Skill names MUST NOT be shown, and there SHALL be no feedback until the end. The board and calculator SHALL be available.

#### Scenario: Lesson with four skills
- **WHEN** a quiz is drawn for a lesson with four skills
- **THEN** it has 15 questions and every skill has at least three

## ADDED Requirements

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
