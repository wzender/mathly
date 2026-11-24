## ADDED Requirements

### Requirement: The AI chat in the practice rounds
The system SHALL offer the AI tutor's chat in a lesson round, a mistakes round and a round on the go, about the round's question on screen or one it has answered, and SHALL refuse a question the round has not reached.

#### Scenario: Asking in a lesson round
- **WHEN** a student in a lesson round asks the AI about the question on screen
- **THEN** the AI's reply appears and does not reveal the right choice

#### Scenario: A question not reached yet
- **WHEN** the request names a later question of the round
- **THEN** it is refused

### Requirement: A round's answer after asking does not count for mastery
The system SHALL record a round's answer as not counted for mastery when the student asked the tutor about that question the same day before answering.

#### Scenario: Asked, then answered right
- **WHEN** the student asks about the question on screen and then answers it right
- **THEN** the answer is kept as not counted
