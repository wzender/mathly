# student-home Specification

## Purpose
The first screen of a subject, opened from its card: what to do today in one obvious button, the nearest test and its readiness, and a way back into the path.

## Requirements

### Requirement: Today's task
The home SHALL show, for the nearest test, the days left, the readiness meter and one task for today taken from the countdown plan, as a single obvious button that opens that task.

#### Scenario: Exercise test due
- **WHEN** the nearest test is 9 days away and exercise test 1 is not taken
- **THEN** home shows one button that opens exercise test 1

### Requirement: Required simulation
While the simulation of an upcoming test is open and not taken, home SHALL show it as required.

#### Scenario: Window open
- **WHEN** a test is 4 days away and the student has not taken its simulation
- **THEN** home shows the simulation marked as required

### Requirement: Continue the path
Home SHALL have a button that opens the path's next skill.

#### Scenario: No test
- **WHEN** a student has no upcoming test
- **THEN** home shows the button to continue at the next skill

### Requirement: Tab bar
The student's screens (home, path, submissions "הגשות", grades, collection) SHALL be reachable from a tab bar at the bottom of the screen.

#### Scenario: Switching
- **WHEN** a student taps "ציונים" in the tab bar
- **THEN** the grades screen opens

#### Scenario: The new tab
- **WHEN** a student taps "הגשות" in the tab bar
- **THEN** the submissions screen opens

### Requirement: Home shows only what is critical
The home SHALL show only: the nearest test with its readiness and today's task, a required simulation, the new assignments (not handed in yet), and the button that continues the path. Other tests, assignments that were handed in or checked, and settings such as notifications SHALL NOT be on home; the other tests are reached from the test's card.

#### Scenario: Nothing critical
- **WHEN** a student has no upcoming test and no new assignment
- **THEN** home shows only the button that continues the path

#### Scenario: Two tests
- **WHEN** a student has two upcoming tests
- **THEN** home shows the nearest one, and the other is listed on that test's card
