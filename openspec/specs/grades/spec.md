# grades Specification

## Purpose
One grade scale and one rule for timed attempts across quizzes, exercise tests, the simulation and assignments, and the screen where a student sees all their grades.

## Requirements

### Requirement: One grade scale
Every grade SHALL be a whole number from 0 to 100. In a multiple-choice quiz or test every question SHALL be worth the same, and the grade SHALL be the share of right answers, rounded.

#### Scenario: Seven of ten
- **WHEN** a student answers 7 of 10 questions correctly
- **THEN** the grade is 70

#### Scenario: Eight of twelve
- **WHEN** a student answers 8 of 12 questions correctly
- **THEN** the grade is 67

### Requirement: When time ends
When the timer of a timed attempt ends, the server SHALL submit it as it stands, and unanswered questions SHALL count as wrong. Closing or refreshing the app MUST NOT stop or reset the timer.

#### Scenario: Closed the app
- **WHEN** a student closes the app 5 minutes into a 15-minute quiz and opens it 20 minutes later
- **THEN** the quiz has been submitted with the answers given

### Requirement: Grades screen
The student SHALL have a grades screen listing every grade they have: each lesson's quiz (best grade), and every exercise test, simulation and assignment grade as those exist.

#### Scenario: After a quiz
- **WHEN** a student finishes a lesson's quiz
- **THEN** the grades screen shows that lesson's best quiz grade
