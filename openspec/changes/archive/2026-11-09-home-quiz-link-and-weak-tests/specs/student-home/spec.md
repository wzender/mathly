## MODIFIED Requirements

### Requirement: Home shows only what is critical
The home SHALL show only: the nearest test with its readiness and today's task, a required simulation, the lessons behind the curriculum, the practice tests below the pass line, the new assignments (not handed in yet), and the button that continues the path. Other tests, assignments that were handed in or checked, and settings such as notifications SHALL NOT be on home; the other tests are reached from the test's card.

#### Scenario: Nothing critical
- **WHEN** a student has no upcoming test, no new assignment, no lesson behind and no weak practice test
- **THEN** home shows only the button that continues the path

#### Scenario: Two tests
- **WHEN** a student has two upcoming tests
- **THEN** home shows the nearest one, and the other is listed on that test's card

### Requirement: Lessons behind on home
Home SHALL list every lesson behind the curriculum, the earliest date first, with its name, the date it should have been completed by and one link to its בוחן, which shows the best grade so far and that 13 right out of 15 is needed. A completed lesson, a lesson with no date and a lesson whose date is ahead SHALL NOT be listed, and with none behind there SHALL be no such card.

#### Scenario: Two lessons behind
- **WHEN** two lessons have passed their dates and are not completed
- **THEN** home lists both, the one with the earlier date first, each with a link to its בוחן

#### Scenario: Only the בוחן
- **WHEN** a lesson is listed as behind
- **THEN** its row has no option to finish its skills, only the link to the בוחן

#### Scenario: The grade
- **WHEN** the student's best grade in that lesson's בוחן is 80
- **THEN** the row shows 80 and says that 13 right out of 15 is needed

#### Scenario: Caught up
- **WHEN** a student passes the בוחן of a lesson that was behind
- **THEN** the lesson is no longer listed on home

#### Scenario: None behind
- **WHEN** no lesson is behind
- **THEN** home has no behind card

## ADDED Requirements

### Requirement: Practice tests below the pass line
Home SHALL list the practice tests of the student's upcoming tests that were taken and whose best grade is below 87 (13 right out of 15): the test's date, which practice test, the best grade and a link to take it again. A practice test not taken yet, or with a best grade of 87 or more, SHALL NOT be listed, and with none there SHALL be no such card.

#### Scenario: A weak one
- **WHEN** a student's best grade in practice test 1 for a test on the 16th is 25
- **THEN** home lists practice test 1 for that test with 25 and a link to take it again

#### Scenario: Good enough
- **WHEN** the best grade is 87 or more
- **THEN** it is not listed

#### Scenario: Not taken
- **WHEN** a practice test was not taken yet
- **THEN** it is not listed

#### Scenario: Retaken
- **WHEN** the student retakes it and the best grade reaches 87
- **THEN** it is no longer listed

## REMOVED Requirements

### Requirement: Two ways to catch up
**Reason**: The behind-lessons card only links to the בוחן now; finishing all the skills is no longer offered on home.
**Migration**: Remove the skills option and the next-skill data from the card; the lesson's skills are still on the path.
