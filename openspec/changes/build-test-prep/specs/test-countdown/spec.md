# Spec Delta

## Purpose

Plans the student's last days before a real test: finish the path, take two exercise tests, take the simulation, then review what failed, with one clear task for today.

## ADDED Requirements

### Requirement: Countdown plan
Once a test is set, the student SHALL see a plan based on days left: until ~9 days, finish the path for every covered lesson; ~9, exercise test 1; ~7, exercise test 2; ~5, the required simulation test; 4 to 1, review the skills that failed in the simulation, with light mixed review the day before.

#### Scenario: Plan at 12 days
- **WHEN** a test is set 12 days ahead
- **THEN** the plan shows finishing the covered skills now, exercise test 1 at ~9 days, exercise test 2 at ~7, the simulation at ~5 and review in the last 4 days

### Requirement: Days are recommendations
The plan's day numbers SHALL be recommendations. The student SHALL be able to start each step earlier or later.

#### Scenario: Starting early
- **WHEN** a student opens exercise test 2 with 11 days left
- **THEN** the exercise test starts

### Requirement: Short notice shortens the gaps
If a test is set less than 9 days ahead, the plan SHALL keep the same order of steps and shorten the gaps between them evenly.

#### Scenario: Test in 6 days
- **WHEN** a test is set 6 days ahead
- **THEN** the plan keeps the order exercise test 1, exercise test 2, simulation, review, spread evenly over the 6 days

### Requirement: Today's task
Home SHALL show, for the nearest test, the days left, the readiness meter and one task for today taken from the plan, as a single obvious button. When several tests are coming up, today's task SHALL come from the closest one.

#### Scenario: Two tests ahead
- **WHEN** a student has tests in 4 and 10 days
- **THEN** home shows one task for today, taken from the plan of the test in 4 days
