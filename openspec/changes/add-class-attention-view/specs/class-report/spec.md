# Spec Delta

## Purpose

Gives the class teacher a view of their students that shows at a glance who needs help and why, where the class as a whole is stuck, and how each student's activity is changing.

## ADDED Requirements

### Requirement: Report lists students who need attention
The class report SHALL open with a "needs attention" section listing every student who matches at least one attention signal, with each matched signal stated in words. Students with a progress record and no signal MUST NOT appear in it. When no student matches, the section SHALL say so.

#### Scenario: Inactive student
- **WHEN** a student's last practice day is 8 days ago
- **THEN** the student appears in the section with the reason "לא תרגל 8 ימים"

#### Scenario: Stuck on a skill
- **WHEN** a student has 3 or more wrong answers in skill `t_ext` in the last 14 days and has not finished `t_ext`
- **THEN** the student appears with a reason naming that skill

#### Scenario: Activity dropped
- **WHEN** a student had 20 correct answers last week and 6 this week
- **THEN** the student appears with a reason saying their practice dropped

#### Scenario: Small numbers are not a drop
- **WHEN** a student had 8 correct answers last week and 2 this week
- **THEN** the drop signal does not apply to them

#### Scenario: Low unit-quiz grade
- **WHEN** a student's latest server-graded unit-quiz grade in a class unit is below 55
- **THEN** the student appears with a reason naming the unit and the grade

#### Scenario: Never practised
- **WHEN** a student has signed in but has no saved progress
- **THEN** the student appears with the reason that they have not started practising

#### Scenario: Nobody needs attention
- **WHEN** no student matches any signal
- **THEN** the section says that no student needs attention right now

### Requirement: Students × skills grid
The report SHALL offer a grid for a unit the teacher chooses among the class's units: one row per student, one column per skill of the unit. Each cell SHALL show the skill's state for that student: gold, finished, fading, practising (tried but not finished) or not started.

#### Scenario: Teacher opens the grid
- **WHEN** the teacher opens the grid and chooses unit `t`
- **THEN** each student row shows one cell per skill of `t`, coloured by state, with the state also given as text for screen readers

#### Scenario: Fading cell
- **WHEN** a student finished a skill but has not practised it for longer than the fading period used on the student's own path
- **THEN** the cell shows the fading state, the same state the student sees on their own path

### Requirement: Grid shows class-wide difficulties
Each skill column in the grid SHALL show how many students finished it. A column where at least a third of the students with progress are practising the skill without finishing it SHALL be marked as a class-wide difficulty.

#### Scenario: Class stuck on a skill
- **WHEN** 12 of 27 students with progress have tried `g_pyth` without finishing it
- **THEN** the `g_pyth` column is marked as a class-wide difficulty and shows how many students finished it

### Requirement: Units overview
The grid SHALL also offer an overview with one column per class unit, each cell showing how many of the unit's skills the student finished out of the unit's total.

#### Scenario: Overview
- **WHEN** the teacher opens the units overview
- **THEN** each student row shows, for every class unit, finished skills out of total skills

### Requirement: Weekly activity on a student's card
Each student's card SHALL show the correct answers of the current week and of the previous week, taken from the student's per-day practice counts.

#### Scenario: Two weeks of practice
- **WHEN** a student answered 14 questions correctly this week and 22 last week
- **THEN** their card shows 14 for this week and 22 for last week

### Requirement: Teacher can sort the student list
The teacher SHALL be able to sort the student list by attention (most signals first), name, progress (finished skills) or last activity. The chosen order SHALL be kept on that device when the report is opened again.

#### Scenario: Sort by last activity
- **WHEN** the teacher chooses to sort by last activity
- **THEN** the students who practised longest ago come first

### Requirement: Students are shown by name
The report SHALL show each student by the nickname set for them in the class, otherwise by their Google account name, otherwise by the part of their email before the @. The full email SHALL stay visible inside the student's card.

#### Scenario: Class nickname set
- **WHEN** the class has the nickname "נועה ל." for a student
- **THEN** the report shows "נועה ל." for that student everywhere in the report

#### Scenario: No nickname
- **WHEN** a student has no class nickname and their Google name is "Noa Levi"
- **THEN** the report shows "Noa Levi"
