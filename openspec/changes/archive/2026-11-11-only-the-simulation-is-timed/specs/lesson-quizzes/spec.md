## MODIFIED Requirements

### Requirement: Quiz format
A quiz SHALL be 15 multiple-choice questions drawn from the bank questions of the lesson's skills, at least one per skill and the rest spread evenly. It SHALL have no time limit: it stays open until the student hands it in. Skill names MUST NOT be shown, and there SHALL be no feedback until the end. The board and calculator SHALL be available.

#### Scenario: Lesson with four skills
- **WHEN** a quiz is drawn for a lesson with four skills
- **THEN** it has 15 questions and every skill has at least three

#### Scenario: No time limit
- **WHEN** a student starts a quiz and comes back to it an hour later
- **THEN** it shows no timer and is still open with the answers given
