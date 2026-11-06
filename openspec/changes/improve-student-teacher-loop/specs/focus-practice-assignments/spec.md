# Spec Delta

## Purpose

Lets a class teacher give skill practice to chosen students of their class, so the weaknesses found in the report turn into work each student sees, while class-wide skill and quiz assignments stay with managers.

## ADDED Requirements

### Requirement: Class teacher gives focus practice to chosen students
The class teacher of a class SHALL be able to create a focus-practice assignment for 1 or more chosen students of that class, with a title of up to 80 characters, an optional note of up to 500 characters, a due date and 1 to 5 skill items of the class's units. Any other item kind in a teacher's focus-practice assignment MUST be rejected.

#### Scenario: Focus practice for two students
- **WHEN** the teacher of 9א gives "חיזוק פיתגורס" with skills `g_pyth` and `g_pyth_word` to Dana and Noa, due 15/11
- **THEN** the assignment is stored for 9א with those two students as its audience

#### Scenario: Quiz item refused
- **WHEN** the teacher adds a unit-quiz item to a focus-practice assignment
- **THEN** the server rejects it with "teachers_give_worksheets_only"

#### Scenario: Student of another class
- **WHEN** the chosen students include a student who is not in 9א
- **THEN** the server rejects the assignment

### Requirement: Class-wide skill items stay with managers
A class teacher's assignment for the whole class SHALL keep accepting worksheet items only; skill, unit-quiz and practice-exam items for the whole class SHALL stay limited to managers.

#### Scenario: Whole-class skill assignment by a teacher
- **WHEN** a class teacher who is not a manager saves a whole-class assignment with a skill item
- **THEN** the server rejects it

### Requirement: Only the chosen students see a focus assignment
A focus-practice assignment SHALL appear only to its chosen students, on the task list, the home screen and the path markers. Other students of the class MUST NOT receive it in any response.

#### Scenario: Classmate not chosen
- **WHEN** Yossi of 9א loads his assignments
- **THEN** "חיזוק פיתגורס" given to Dana and Noa is not in the response

### Requirement: Teacher follows focus practice
The assignments tab of the class report SHALL list focus-practice assignments marked as personal, with their audience, and SHALL count completion only over their chosen students. A student's card SHALL list the focus practice given to them and its state.

#### Scenario: Completion count
- **WHEN** Dana finished both skills and Noa finished one
- **THEN** the report shows "1 מתוך 2 סיימו" for "חיזוק פיתגורס"

### Requirement: Teacher changes the audience
The class teacher SHALL be able to add or remove chosen students of a focus-practice assignment. A removed student SHALL no longer see it; an added student SHALL see it on their next load.

#### Scenario: Student added
- **WHEN** the teacher adds Yossi to "חיזוק פיתגורס"
- **THEN** Yossi sees it after reloading, with its due date
