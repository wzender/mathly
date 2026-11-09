## ADDED Requirements

### Requirement: Teacher tabs show how many
Each tab of a teacher's screen SHALL show the number of items in it: the classes they teach, their classes' tests, their assignments, and the submissions waiting in the inbox.

#### Scenario: Counts
- **WHEN** a teacher teaches 2 classes with 3 tests and 4 assignments, and 5 submissions wait
- **THEN** the tabs show 2, 3, 4 and 5 next to their names

#### Scenario: Nothing waiting
- **WHEN** no submission waits
- **THEN** the inbox tab shows 0
