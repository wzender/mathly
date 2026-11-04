# Spec Delta

## Purpose

Lets a class teacher give their class practice to do in the app by a date, shows students what to do next, and shows the teacher who did it.

## ADDED Requirements

### Requirement: Class teacher creates assignments
The class teacher of a class, or a manager, SHALL be able to create an assignment for that class with a title of up to 80 characters, an optional note of up to 500 characters, a due date, and at least one item. An item is a skill, a unit quiz, or a practice exam over chosen units, and it MUST belong to the class's units. Any other account MUST be refused.

#### Scenario: Teacher creates an assignment
- **WHEN** the teacher of 9א creates "חזרה לפני המבחן" due 12/11 with skills `g_pyth` and `g_pyth_word` and the unit quiz of unit `g`
- **THEN** the assignment is stored for 9א with its three items and its due date

#### Scenario: Item outside the class's units
- **WHEN** the teacher adds a skill from a unit that is not open to the class
- **THEN** the server rejects the assignment

#### Scenario: Not the class teacher
- **WHEN** a student or a teacher of another class tries to create an assignment for 9א
- **THEN** the server refuses with a forbidden error

#### Scenario: No items
- **WHEN** the teacher saves an assignment with no items
- **THEN** the server rejects it

### Requirement: Teacher edits and deletes assignments
The class teacher or a manager SHALL be able to change an assignment's title, note, due date and items, or delete it. Students SHALL see the change the next time their page loads assignments.

#### Scenario: Due date moved
- **WHEN** the teacher moves the due date from 12/11 to 14/11
- **THEN** students of the class see 14/11 after reloading

#### Scenario: Assignment deleted
- **WHEN** the teacher deletes an assignment
- **THEN** it no longer appears to students or in the report

### Requirement: Students see their open assignments
A student SHALL see on their home screen the assignments of their classes that are not finished, with title, note, due date, items, and how many items are done. An assignment past its due date and not finished SHALL be marked as late. Finished assignments SHALL appear in a separate done list for 14 days after their due date.

#### Scenario: Open assignment
- **WHEN** a student has an assignment with 3 items, 1 done, due in 2 days
- **THEN** the home screen shows it with "1 מתוך 3" and the due date

#### Scenario: Late assignment
- **WHEN** the due date has passed and an item is not done
- **THEN** the assignment is shown as late

#### Scenario: Next item
- **WHEN** the student presses the assignment's continue button
- **THEN** the app opens the first unfinished item (the skill sheet, the unit quiz introduction or a practice exam set to the chosen units)

### Requirement: Item completion rules
A skill item SHALL be done when the student has finished the skill, whenever that happened. A unit-quiz item SHALL be done when the server has a sitting of that unit's quiz from the student submitted after the assignment was created. A practice-exam item SHALL be done when the student took a practice exam after the assignment was created that included all the item's units.

#### Scenario: Skill finished before the assignment
- **WHEN** a student finished `g_pyth` last week and an assignment with `g_pyth` is created today
- **THEN** that item is already done for the student

#### Scenario: Old unit-quiz sitting
- **WHEN** the student's only sitting of unit `g` was submitted before the assignment was created
- **THEN** the unit-quiz item is not done

#### Scenario: Practice exam missing a unit
- **WHEN** the item asks for a practice exam over units `t` and `g`, and the student took one over `t` only
- **THEN** the item is not done

### Requirement: Assigned skills are marked on the path
Skills that are items of an open assignment SHALL carry a marker on the student's path, with an accessible label naming the assignment.

#### Scenario: Marker
- **WHEN** `g_pyth` is in an open assignment that the student has not finished
- **THEN** its star on the path has the assignment marker

### Requirement: Teacher follows assignment completion
The class report SHALL list the class's assignments with how many students finished each, and for each assignment the students with each item's state: done, not done, or done late (finished after the due date, for items with a completion time).

#### Scenario: Teacher opens an assignment
- **WHEN** the teacher opens "חזרה לפני המבחן" in the report's assignments tab
- **THEN** they see "18 מתוך 27 סיימו" and a row per student showing which items are done

### Requirement: Overdue assignments raise attention
A student with an assignment past its due date and not finished SHALL appear in the report's "needs attention" section, with a reason naming the assignment.

#### Scenario: Overdue
- **WHEN** a student has not finished an assignment whose due date was yesterday
- **THEN** the student appears in "needs attention" with the reason naming that assignment
