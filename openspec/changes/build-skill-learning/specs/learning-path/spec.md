# Spec Delta

## Purpose

Gives the student a self-paced path through every lesson (שיעור) and skill, open in any order, with a daily goal and streak and a collection of what they achieved.

## ADDED Requirements

### Requirement: All lessons open
The student SHALL be able to open any lesson, and any skill inside it, at any time and in any order. Lessons MUST NOT be locked, and the app MUST NOT force an order.

#### Scenario: Jumping ahead
- **WHEN** a student who has not started the first lesson opens a skill in a later lesson
- **THEN** the skill opens at its first stage

### Requirement: Path screen
The path screen SHALL list all lessons and their skills, each skill showing its state (not started, learning or mastered). Mastered skills SHALL look clearly different from learning and not-started ones.

#### Scenario: Viewing the path
- **WHEN** a student opens the path
- **THEN** every lesson is listed with its skills, and each skill shows its state

### Requirement: Daily goal and streak
A day with 5 correct answers SHALL count toward the student's streak. The path SHALL show the day's progress toward 5 and the current streak.

#### Scenario: Goal reached
- **WHEN** a student answers a fifth question correctly today
- **THEN** today's goal is shown as reached and the streak counts today

#### Scenario: Goal missed
- **WHEN** a student has 3 correct answers today
- **THEN** today's goal shows 3 of 5 and today does not yet count toward the streak

### Requirement: Collection screen
The student SHALL have a collection screen that shows each skill they mastered and each lesson they completed.

#### Scenario: New mastery
- **WHEN** a student masters a skill
- **THEN** the skill appears on their collection screen
