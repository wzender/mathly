# Spec Delta

## MODIFIED Requirements

### Requirement: Manager creates classes
A manager (or a developer) SHALL create, edit and delete classes. A class SHALL have a name (1–80 characters, unique ignoring case), its students, at most one teacher (an email, never also a student of that class), the subjects it studies (math by default), an AI switch that starts off, and a daily AI budget (default 150). A class SHALL NOT have chosen lessons: a class studies every published lesson of its subjects.

#### Scenario: New class
- **WHEN** a manager creates "ט'3" with a teacher and 25 students
- **THEN** "ט'3" appears in the class list with that teacher and 25 students, studying math, its AI switch is off, and the form never asked for lessons

#### Scenario: A class with two subjects
- **WHEN** a manager creates "ט'4" and ticks math and "מדעים"
- **THEN** "ט'4" studies both subjects

#### Scenario: Teacher listed as a student
- **WHEN** a manager names "t@school.org" as the teacher and also lists it as a student of the same class
- **THEN** the class is not saved and the manager is told why

#### Scenario: A refused save keeps what was typed
- **WHEN** a manager changes a class's name and teacher, presses save at the bottom of the form, and the save is refused
- **THEN** the reason is shown next to the save button and in view, the typed name and teacher are still in the form, and nothing was saved

### Requirement: A student's lessons
A student who belongs to at least one class SHALL have every published lesson of every subject their classes study, whatever lessons were stored for their classes before. A student in no class has none.

#### Scenario: Two classes, different lessons
- **WHEN** a student is in one class stored with lessons A and B and another stored with B and C, and both study math only
- **THEN** the student's lessons are every math lesson

#### Scenario: A class saved with some lessons
- **WHEN** a student is in a class that was saved earlier with only lessons A and B, and studies math
- **THEN** the student's path has every math lesson

#### Scenario: Two classes, two subjects
- **WHEN** a student is in a class studying math and another studying "מדעים"
- **THEN** the student has every math lesson and every published "מדעים" lesson

#### Scenario: No class
- **WHEN** a student who is in no class signs in
- **THEN** they see no lessons
