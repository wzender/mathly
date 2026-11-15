## ADDED Requirements

### Requirement: Deepening counts
The readiness number SHALL start from deepening: the share of the test's skills the student has mastered, from 0 to 100, closes 20% of the gap from 0. The handed-in tests SHALL then move it from there, oldest first, as before, so mastering more skills raises the number whatever tests came after, and the test's page SHALL say how much deepening gives now.

#### Scenario: Half the material
- **WHEN** a student has mastered half of the test's skills and taken no test
- **THEN** the readiness number is 10

#### Scenario: Then a simulation
- **WHEN** that student hands in a simulation with 80
- **THEN** the number is 52 (10, then 60% of the way to 80)
