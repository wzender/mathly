## MODIFIED Requirements

### Requirement: Lessons behind on home
Home SHALL list every lesson behind the curriculum, the earliest date first, kept short: its name, the date it should have been completed by, a link named only "בוחן", and the best בוחן grade as a bare number, or "-" when there is none. The row MUST NOT explain what passes the בוחן. A completed lesson, a lesson with no date and a lesson whose date is ahead SHALL NOT be listed, and with none behind there SHALL be no such card.

#### Scenario: Two lessons behind
- **WHEN** two lessons have passed their dates and are not completed
- **THEN** home lists both, the one with the earlier date first, each with a link to its בוחן

#### Scenario: Only the בוחן
- **WHEN** a lesson is listed as behind
- **THEN** its row has no option to finish its skills, only the link to the בוחן

#### Scenario: The grade
- **WHEN** the student's best grade in that lesson's בוחן is 80
- **THEN** the row shows 80 and no other text about the grade

#### Scenario: No grade
- **WHEN** the student has not taken that בוחן
- **THEN** the row shows "-"

#### Scenario: Caught up
- **WHEN** a student passes the בוחן of a lesson that was behind
- **THEN** the lesson is no longer listed on home

#### Scenario: None behind
- **WHEN** no lesson is behind
- **THEN** home has no behind card

### Requirement: Practice tests below the pass line
Home SHALL list the practice tests of the student's upcoming tests that were taken and whose best grade is below 87 (13 right out of 15), kept short: which practice test, its test's date, the link to take it again and the best grade as a bare number. A practice test not taken yet, or with a best grade of 87 or more, SHALL NOT be listed, and with none there SHALL be no such card.

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
