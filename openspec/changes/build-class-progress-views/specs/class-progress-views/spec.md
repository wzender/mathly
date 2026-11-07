# Spec Delta

## Purpose

Gives the teacher a per-student picture of the class: a heat map of skill states and a table of lesson coverage, each by school period.

## ADDED Requirements

### Requirement: Class heat map
The teacher SHALL see a heat map with a row per student and a column per skill, grouped by lesson. Each cell SHALL be colored by the skill state and also show a symbol or text, so it does not rely on color alone and reads in light and dark mode.

#### Scenario: Reading a cell
- **WHEN** a student is "learning" a skill
- **THEN** that cell has the learning color and the learning symbol

### Requirement: Lesson coverage
The teacher SHALL see a table with a row per student and a column per lesson. Each cell SHALL show the percentage of the lesson's skills the student mastered and their best quiz grade for that lesson.

#### Scenario: Coverage cell
- **WHEN** a student mastered 3 of 4 skills of a lesson and their best quiz grade is 80
- **THEN** the cell shows 75% and 80

### Requirement: Period tabs
Both views SHALL have period tabs "Sep–Dec" and "Jan–Jun". A period SHALL show the skills or lessons taught in it, with states as they were at the end of the period, or today for the current period.

#### Scenario: Past period
- **WHEN** in February a teacher opens the "Sep–Dec" tab
- **THEN** it shows the lessons taught September to December, with states as of the end of December

### Requirement: Works on a computer
The heat map and coverage views SHALL work well on a computer screen as well as on a phone.

#### Scenario: Wide class
- **WHEN** a teacher opens the heat map of 30 students on a laptop
- **THEN** all rows and the lesson-grouped skill columns can be read and scrolled
