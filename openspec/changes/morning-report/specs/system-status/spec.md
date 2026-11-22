## ADDED Requirements

### Requirement: Morning report
The system SHALL report one Israel day (yesterday by default) in counts only: practice answers and how many were right, the people who practised, the attempts started and finished by kind, each class's students, active students and answers, and the seven days up to it. It SHALL NOT carry a student's name or email.

#### Scenario: Yesterday
- **WHEN** a student answered six practice questions yesterday, five of them right, and finished a round on the go
- **THEN** the report shows 6 answers, 5 right, 1 person, and one on-the-go round started and finished

### Requirement: Who reads the report
The developer SHALL read the report, and so SHALL a request with the report key set in the server's settings; anyone else SHALL be refused, and without a key set only the developer SHALL read it.

#### Scenario: A teacher
- **WHEN** a teacher asks for the report
- **THEN** it is refused
