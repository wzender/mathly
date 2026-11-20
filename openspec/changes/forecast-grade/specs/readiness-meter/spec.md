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

### Requirement: Finding the league
Until the student has 15 answers on the test's material, home SHALL show "מגלים את הליגה שלך" with a bar of the answers so far out of 15 that only fills, and no forecast grade, so a first low guess is never shown.

#### Scenario: Day one
- **WHEN** a student who has answered nothing opens home before a test
- **THEN** the strip says "מגלים את הליגה שלך" with 0/15, and no grade

### Requirement: Leagues
After the placement, the student SHALL see a league by the forecast grade (🌙 ירח below 55, 🪐 כוכב לכת from 55, ⭐ כוכב from 70, 🌌 גלקסיה from 85) with the points to the next league, a bar across the current league, and the forecast grade small at the side. The teacher SHALL see the forecast grade and its range as numbers.

#### Scenario: Revealed
- **WHEN** a student reaches 15 answers on the test's material with a forecast of 73
- **THEN** home cheers "נחשפה הליגה שלך: ⭐ כוכב" and shows 12 points to 🌌 גלקסיה

### Requirement: Moving between leagues
Every move up SHALL be cheered. A league SHALL be kept through a dip of less than 3 points below its floor, and a drop SHALL be shown without a cheer or a badge.

#### Scenario: A small dip
- **WHEN** a student shown ⭐ כוכב (from 70) falls to a forecast of 68
- **THEN** home still shows ⭐ כוכב

#### Scenario: Going up
- **WHEN** a student's forecast passes 70 from 66
- **THEN** home cheers "עליתם לליגת ⭐ כוכב"

### Requirement: Where the forecast shows
Home's test strip SHALL show the placement or the league in place of the readiness number, counting up with "+N" when the forecast grew since it was last seen on the device. The result of a lesson round and the test's page SHALL show it (the test's page with the forecast grade and its range), and the teacher's tests tab SHALL show each student's forecast.

#### Scenario: After practice
- **WHEN** a student answers right on the test's skills and opens home again
- **THEN** the forecast grade counts up with "+N"
