# test-countdown Specification

## Purpose
Plans a student's last weeks before a real test, so they finish the path, practise under test conditions, take one simulation and review what failed, without planning it themselves.

## Requirements

### Requirement: The countdown plan
From the moment a test is set, every student of the class SHALL see a plan by days left: until 9, finish the path for the covered lessons; about 9, exercise test 1; about 7, exercise test 2; about 5, the simulation; 4 to 1, review the skills that failed in the simulation, with light mixed review the day before.

#### Scenario: Twelve days ahead
- **WHEN** a test is 12 days away
- **THEN** the plan asks the student to finish the path for the covered lessons

### Requirement: The days are recommendations
The student SHALL be able to start any step earlier or later than its day.

#### Scenario: Early exercise test
- **WHEN** a student opens exercise test 1 eleven days before the test
- **THEN** it starts

### Requirement: Short notice
When a test is set less than 9 days ahead, the plan SHALL keep the same order and shorten the gaps evenly.

#### Scenario: Six days ahead
- **WHEN** a test is set 6 days ahead
- **THEN** the plan still runs path, exercise test 1, exercise test 2, simulation, review, in that order, within the 6 days

### Requirement: Several tests
When several tests are coming up, today's task SHALL come from the closest one.

#### Scenario: Two tests
- **WHEN** a student has tests in 4 and in 10 days
- **THEN** today's task comes from the test in 4 days
