## MODIFIED Requirements

### Requirement: Tab bar
The student's screens (home, path, submissions "הגשות", grades, collection) SHALL be reachable from a tab bar at the bottom of the screen.

#### Scenario: Switching
- **WHEN** a student taps "ציונים" in the tab bar
- **THEN** the grades screen opens

#### Scenario: The new tab
- **WHEN** a student taps "הגשות" in the tab bar
- **THEN** the submissions screen opens

## ADDED Requirements

### Requirement: Home shows only what is critical
The home SHALL show only: the nearest test with its readiness and today's task, a required simulation, the new assignments (not handed in yet), and the button that continues the path. Other tests, assignments that were handed in or checked, and settings such as notifications SHALL NOT be on home; the other tests are reached from the test's card.

#### Scenario: Nothing critical
- **WHEN** a student has no upcoming test and no new assignment
- **THEN** home shows only the button that continues the path

#### Scenario: Two tests
- **WHEN** a student has two upcoming tests
- **THEN** home shows the nearest one, and the other is listed on that test's card
