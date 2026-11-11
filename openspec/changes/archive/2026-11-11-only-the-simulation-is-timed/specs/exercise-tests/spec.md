## MODIFIED Requirements

### Requirement: Like the real test
An exercise test SHALL have the real test's number of questions, mix questions from all the covered lessons, hide skill names, and give feedback only at the end. It SHALL have no time limit: only the simulation is timed.

#### Scenario: During the test
- **WHEN** a student answers a question in an exercise test
- **THEN** no right or wrong is shown until the test ends

#### Scenario: No timer
- **WHEN** a student starts an exercise test of a real test set for 30 minutes
- **THEN** it shows no timer and stays open until the student hands it in
