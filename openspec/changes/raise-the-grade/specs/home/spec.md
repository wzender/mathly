## ADDED Requirements

### Requirement: A button that lists the ways to raise the grade
The system SHALL show in the nearest test's block a button that opens a sheet of the ways to raise the estimated grade, each with what it does and a link to it: today's mission, the rounds that add the most with their points, closing the gaps when lessons are behind, a practice test, the simulation and quick practice.

#### Scenario: Opening the sheet
- **WHEN** a student with a test in 10 days and a lesson behind taps the button
- **THEN** the sheet shows today's mission with its progress, rounds with "+N", closing the gaps, a practice test and the simulation

#### Scenario: Following a way
- **WHEN** the student taps a round in the sheet
- **THEN** the sheet closes and that lesson's round opens
