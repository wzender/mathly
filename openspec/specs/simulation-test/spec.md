# simulation-test Specification

## Purpose
One full rehearsal of the real test a few days before it, so the student knows where they stand while there is still time to fix the gaps it finds.

## Requirements

### Requirement: Required, one attempt
Every student SHALL take one simulation per real test, and it SHALL be possible to take it only once.

#### Scenario: Second try
- **WHEN** a student who finished the simulation opens it again
- **THEN** they see their result and cannot start it again

### Requirement: Like the real test
The simulation SHALL cover all the lessons of the real test, with its number of questions and time limit, no skill names and no feedback until the end.

#### Scenario: Length
- **WHEN** the real test has 12 questions and 45 minutes
- **THEN** the simulation has 12 questions and 45 minutes

### Requirement: Window
The simulation SHALL be open from about 5 days before the test until the test day, and SHALL be shown as required on the student's home until it is taken.

#### Scenario: Too early
- **WHEN** a student opens the simulation 8 days before the test
- **THEN** it says when it opens and does not start

### Requirement: Review tasks
After the simulation the app SHALL list the skills that failed and make them the review tasks of the last days of the countdown.

#### Scenario: Two failed skills
- **WHEN** a student fails two skills in the simulation
- **THEN** those two skills are today's review tasks in the last days
