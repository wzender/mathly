## ADDED Requirements

### Requirement: Forecast grade
For each upcoming test the system SHALL forecast the grade "if the test were today" as the mean, over the test's skills, of each skill's chance of a right answer, with a range that narrows as the answers grow.

#### Scenario: Nothing done
- **WHEN** a student who has answered nothing opens home before a test
- **THEN** the forecast is 30, between 5 and 55

#### Scenario: A bad practice test
- **WHEN** a student hands in a practice test with every answer wrong
- **THEN** the forecast goes down

### Requirement: A skill's chance
A skill's chance SHALL start from its state (not started 30%, learning 50%, mastered 85%) and move with the student's latest answers on it, the newest weighing most and answers in practice tests and the simulation weighing double. A mastered skill SHALL stay at 75% or more, and a faded one SHALL lose a tenth.

#### Scenario: A mastered skill
- **WHEN** a student keeps answering a mastered skill wrong
- **THEN** its chance stays at 75%

### Requirement: Where the forecast shows
Home's test strip SHALL show the forecast with its range in place of the readiness number, counting up with "+N" when it grew since it was last seen on the device; a drop SHALL be shown without a badge. The result of a lesson round and the test's page SHALL show it, and the teacher's tests tab SHALL show each student's forecast.

#### Scenario: After practice
- **WHEN** a student answers right on the test's skills and opens home again
- **THEN** the forecast counts up to its new value with "+N"
