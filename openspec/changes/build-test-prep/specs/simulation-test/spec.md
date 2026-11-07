# Spec Delta

## Purpose

Gives each student one required, one-time full simulation (מבחן סימולציה) of the real test, so they know where they stand while there is still time to fix gaps.

## ADDED Requirements

### Requirement: One required attempt
Every student SHALL take one simulation test per real test. It SHALL be possible to take it only once.

#### Scenario: Second try
- **WHEN** a student who handed in the simulation opens it again
- **THEN** they see their result and cannot start another attempt

### Requirement: Built like the real test
The simulation SHALL cover all lessons of the real test, with the real test's number of questions and time limit, no skill names, and no feedback until the end.

#### Scenario: Taking the simulation
- **WHEN** a student starts the simulation of a test with 12 questions and 90 minutes
- **THEN** it has 12 questions from all covered lessons, a 90-minute limit, no skill names and no feedback until handed in

### Requirement: Window and home reminder
The simulation SHALL become available about 5 days before the test and stay available until the test day. Until taken, it SHALL be shown as required on the student's home screen.

#### Scenario: Too early
- **WHEN** the test is 8 days away
- **THEN** the simulation cannot be started yet

#### Scenario: Required on home
- **WHEN** the test is 4 days away and the student has not taken the simulation
- **THEN** home shows the simulation as required

### Requirement: Timer kept on the server
The simulation's timer SHALL be kept on the server, so refreshing or closing the app does not reset it. The grade SHALL be computed and stored on the server.

#### Scenario: Refresh mid-test
- **WHEN** a student refreshes the app 30 minutes into a 90-minute simulation
- **THEN** the timer shows about 60 minutes left

### Requirement: Failed skills become review tasks
After the simulation, the system SHALL list the skills that failed and make them the review tasks of the plan's last days.

#### Scenario: Review tasks
- **WHEN** a student hands in the simulation with 3 failed skills
- **THEN** the result lists them, and the countdown's last days ask to review those 3 skills
