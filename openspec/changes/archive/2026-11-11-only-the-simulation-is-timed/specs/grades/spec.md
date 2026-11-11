## MODIFIED Requirements

### Requirement: When time ends
The simulation SHALL be the only timed attempt; a lesson quiz and an exercise test have no time limit. When the simulation's timer ends, the server SHALL submit it as it stands, and unanswered questions SHALL count as wrong. Closing or refreshing the app MUST NOT stop or reset the timer.

#### Scenario: Closed the app
- **WHEN** a student closes the app 5 minutes into a 15-minute simulation and opens it 20 minutes later
- **THEN** the simulation has been submitted with the answers given

#### Scenario: A quiz is not timed
- **WHEN** a student closes the app 5 minutes into a lesson quiz and opens it an hour later
- **THEN** the quiz is still open with the answers given
