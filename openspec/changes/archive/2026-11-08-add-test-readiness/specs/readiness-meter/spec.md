# Spec Delta

## Purpose

Shows the student and the teacher, as one honest number, how ready the student is for an upcoming test, and what it is made of.

## ADDED Requirements

### Requirement: One readiness number
For each upcoming test the app SHALL show the student and the teacher a number from 0 to 100, drawn as a level bar, with its parts under it: M, the % of covered skills mastered; E, the average of the best grade of each exercise test taken; S, the simulation grade once taken.

#### Scenario: Parts shown
- **WHEN** a student opens the reminder of a test
- **THEN** the bar shows the number with M, E and S under it

### Requirement: How the number is made
The number SHALL be the weighted average of the parts that exist, with weights M 50, E 20 and S 30; a part that does not exist yet is left out and the others are scaled up.

#### Scenario: Only mastery so far
- **WHEN** a student has mastered 60% of the covered skills and taken no tests
- **THEN** the number is 60

#### Scenario: All three parts
- **WHEN** M is 80, E is 70 and S is 90
- **THEN** the number is 81

### Requirement: No false confidence
Until the simulation is taken the number SHALL be capped at 80, and the bar SHALL say so. The label SHALL be "מתחילים" for 0–39, "בדרך" for 40–69, "כמעט שם" for 70–84 and "מוכנים" for 85–100; "מוכנים" can only show after the simulation.

#### Scenario: Strong before the simulation
- **WHEN** M is 100 and E is 95 and the simulation is not taken
- **THEN** the number shows 80 with a note that the simulation is still missing
