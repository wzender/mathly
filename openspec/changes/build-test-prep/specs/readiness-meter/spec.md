# Spec Delta

## Purpose

Shows the student and the teacher how ready the student is for each upcoming test, from mastered skills, exercise test grades and the simulation grade.

## ADDED Requirements

### Requirement: Readiness meter
For each upcoming test, the system SHALL show a readiness meter made of the percentage of covered skills that are mastered, the best grade of each exercise test, and the simulation grade once taken. Both the student and the teacher SHALL see it.

#### Scenario: Before the simulation
- **WHEN** a student mastered 15 of 20 covered skills and has best grades 70 and 80 on the exercise tests
- **THEN** the meter shows 75% mastered, 70 and 80, and no simulation grade

#### Scenario: Teacher view
- **WHEN** the teacher looks at the student's readiness for that test
- **THEN** the same meter is shown
