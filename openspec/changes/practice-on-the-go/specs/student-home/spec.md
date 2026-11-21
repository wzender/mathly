## ADDED Requirements

### Requirement: Questions that need no board
The system SHALL keep the list of the bank's questions that need no board: those a student who knows the topic answers in their head within about 30 seconds without writing (a definition, a property, which statement is true, reading a figure or a graph, one simple arithmetic step). A question that needs a line of work SHALL NOT be on it.

#### Scenario: An equation
- **WHEN** a question asks to solve x² + 4x − 5 = 0
- **THEN** it is not offered on the go

### Requirement: Practice on the go
When the student's lessons have 10 or more questions that need no board, home SHALL offer practice on the go (beside the practice test and the simulation in the test strip, or in the status row with no test). It SHALL start a round of 10 of them with no board, and an open round SHALL resume.

#### Scenario: On the bus
- **WHEN** a student taps practice on the go
- **THEN** a round of 10 questions opens with no board

### Requirement: The on-the-go round
The round SHALL take at most 2 questions per skill, skills not mastered and the nearest test's lessons first and the least-seen questions first. Each answer SHALL count as a practice answer, and the round SHALL end with the score, what was mastered and what to strengthen, and another round.

#### Scenario: The end
- **WHEN** a student answers the 10 questions
- **THEN** each answer counted as practice, and the result offers "עוד סבב בנסיעה"
