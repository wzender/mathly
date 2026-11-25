## ADDED Requirements

### Requirement: A held estimated grade
The system SHALL show the student, for the nearest test, a held grade that starts 25 above the forecast (at most 100), keeps its lead on each day the daily mission is done, loses a quarter of the lead on each day it is not, is never below the forecast, and is capped within the last 14 days so that it equals the forecast on the test's day.

#### Scenario: Two days without practice
- **WHEN** the forecast is 60 and two days passed without the daily mission
- **THEN** the held grade is 60 + 25 × 0.75² ≈ 74

#### Scenario: Practice every day
- **WHEN** the daily mission was done every day, three weeks before the test
- **THEN** the held grade is the forecast plus 25

### Requirement: Today decides
The system SHALL show beside the held grade whether today's mission is done ("הציון נשמר") or else the grade tomorrow without it, and the mission's progress in answers.

#### Scenario: Not done yet
- **WHEN** today's mission is 20 answers and 7 were answered
- **THEN** home shows "7/20 תשובות" and tomorrow's lower grade without the mission
