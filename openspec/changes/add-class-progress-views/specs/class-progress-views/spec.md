# Spec Delta

## Purpose

Gives a teacher, and a developer, views of a class's progress by skill and by lesson, so they can see at a glance which skills the class struggles with and who needs help.

## ADDED Requirements

### Requirement: Class heat map
For a class they teach, a teacher SHALL see a heat map with a row per student and a column per skill, grouped by lesson. Each cell SHALL show the skill's state (not started, learning, mastered) by color and by a symbol, readable in light and dark mode.

#### Scenario: Reading without color
- **WHEN** the heat map is printed in black and white
- **THEN** every cell's state can still be read from its symbol

### Requirement: Lesson coverage
For a class they teach, a teacher SHALL see a table with a row per student and a column per lesson; each cell SHALL show the % of the lesson's skills the student mastered and their best quiz grade for it.

#### Scenario: Half covered
- **WHEN** a student mastered 2 of a lesson's 4 skills and scored 75 on its quiz
- **THEN** their cell for that lesson shows 50% and 75

### Requirement: Period tabs
Both views SHALL have tabs for Sep–Dec and Jan–Jun. A period SHALL show the skills of the lessons taught in it, with states as they were at the end of the period, or today for the current period.

#### Scenario: Last period
- **WHEN** a teacher opens the Sep–Dec tab in March
- **THEN** each cell shows the state as of 31 December

### Requirement: Readiness per student
For each upcoming test of the class, the teacher SHALL see each student's readiness number and its parts.

#### Scenario: Before a test
- **WHEN** a test is 5 days away
- **THEN** the teacher sees every student's readiness number for it

### Requirement: Works on a computer
The views SHALL use the full width of a computer screen and keep student names and lesson headers visible while scrolling.

#### Scenario: Wide class
- **WHEN** a teacher scrolls the heat map sideways on a computer
- **THEN** the student names stay visible

### Requirement: Developer access
A developer SHALL be able to open these views for any class.

#### Scenario: Any class
- **WHEN** a developer opens the heat map of a class they do not teach
- **THEN** it opens
