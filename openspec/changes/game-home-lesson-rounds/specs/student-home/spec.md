## ADDED Requirements

### Requirement: The lessons map
Home SHALL open with a map of the student's lessons in the subject, in the bank's order, on one winding trail. Each lesson SHALL be a node with its number (a crown and "מושלם" when it has three stars), its name, its stars as ★ and ☆, a "⏰" mark when it is behind the curriculum and a "◐" mark when a round is open. Tapping a node SHALL open the lesson's round over the home. Above the map SHALL be the stars collected out of three per lesson, the lessons perfected, and the daily goal with the streak.

#### Scenario: Opening home
- **WHEN** a student with three lessons opens home
- **THEN** they see three nodes on the trail, each with its stars, and "⭐ N מתוך 9"

#### Scenario: A behind lesson
- **WHEN** a lesson's date has passed and it is not completed
- **THEN** its node shows "⏰" with the date

### Requirement: Play the next lesson
Home SHALL have one big button that opens the round of the next lesson: the lesson with an open round, else the earliest lesson behind the curriculum, else the first lesson with fewer than three stars. With every lesson perfect, it SHALL say so and offer the path for going deeper.

#### Scenario: New student
- **WHEN** a student who answered nothing opens home
- **THEN** the button opens the round of the first lesson

## MODIFIED Requirements

### Requirement: Continue the path
Home SHALL have a link to the path, named for going deeper ("להעמקה").

#### Scenario: No test
- **WHEN** a student has no upcoming test
- **THEN** home shows the map, the play button and the link to the path

### Requirement: Home shows only what is critical
The home SHALL show only: the lessons map with its header and play button, the nearest test with its readiness, today's task and its practice tests below the pass line, a required simulation, the new assignments (not handed in yet), and the link to the path. Other tests, assignments that were handed in or checked, and settings such as notifications SHALL NOT be on home; the other tests are reached from the test's card.

#### Scenario: Nothing critical
- **WHEN** a student has no upcoming test and no new assignment
- **THEN** home shows the map, the play button and the link to the path

#### Scenario: Two tests
- **WHEN** a student has two upcoming tests
- **THEN** home shows the nearest one, and the other is listed on that test's card

## REMOVED Requirements

### Requirement: Lessons behind on home
**Reason**: The map marks a behind lesson on its node, and the play button opens the earliest behind lesson first.
**Migration**: None; the quiz stays on the path.
