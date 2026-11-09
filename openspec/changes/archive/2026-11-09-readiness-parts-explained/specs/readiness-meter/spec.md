## MODIFIED Requirements

### Requirement: One readiness number
For each upcoming test the app SHALL show the student and the teacher a number from 0 to 100, drawn as a level bar, with its three parts under it, each as a row in plain Hebrew with a short line saying what its number is and its value, without the letters M, E and S: mastery, the % of covered skills mastered; practice tests, the average of the best grade of each practice test taken; the simulation, its grade once taken. A part with no value yet SHALL show "—".

#### Scenario: Parts shown
- **WHEN** a student opens the reminder of a test
- **THEN** the bar shows the number with three rows under it: שליטה, מבחני תרגול and סימולציה, each with a short explanation and its value

#### Scenario: No letters
- **WHEN** a student reads the parts
- **THEN** none of the letters M, E and S is shown

#### Scenario: Nothing yet
- **WHEN** no simulation was taken
- **THEN** the simulation row shows "—"
