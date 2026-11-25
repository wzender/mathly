## ADDED Requirements

### Requirement: Every question has a difficulty
The system SHALL keep a difficulty for every bank question (easy, medium or hard) and SHALL treat a question without one as medium.

#### Scenario: A worksheet's question
- **WHEN** a question is not in the difficulty list
- **THEN** it counts as medium

### Requirement: Practice goes from easy to hard
The system SHALL serve a skill's practice round and a lesson round in order of difficulty, easy first, random within a level.

#### Scenario: A skill's round
- **WHEN** a student answers a skill's round to the end
- **THEN** no question comes after a harder one

### Requirement: Tests are medium and up, the simulation harder
The system SHALL draw practice tests from medium and hard questions only with 40% hard ones, and the simulation with 1.5 times that share of hard ones, using easy questions only when the material cannot fill the test otherwise.

#### Scenario: A practice test
- **WHEN** a practice test of 15 questions is drawn from material with enough questions
- **THEN** it has no easy question and about 6 hard ones

#### Scenario: The simulation
- **WHEN** a simulation of 15 questions is drawn
- **THEN** about 9 of them are hard, as far as the material has them
