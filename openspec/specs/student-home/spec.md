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
The student's screens (home, path, grades, collection) SHALL be reachable from a tab bar at the bottom of the screen.

#### Scenario: Switching
- **WHEN** a student taps "ציונים" in the tab bar
- **THEN** the grades screen opens
