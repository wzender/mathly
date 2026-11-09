## MODIFIED Requirements

### Requirement: Manager creates classes
A manager (or a developer) SHALL create, edit and delete classes. A class SHALL have a name (1–80 characters, unique ignoring case), its students, at most one teacher (an email, never also a student of that class), an AI switch that starts off, and a daily AI budget (default 150). A class SHALL NOT have chosen lessons: every class studies every lesson of the bank.

#### Scenario: New class
- **WHEN** a manager creates "ט'3" with a teacher and 25 students
- **THEN** "ט'3" appears in the class list with that teacher and 25 students, its AI switch is off, and the form never asked for lessons

#### Scenario: Teacher listed as a student
- **WHEN** a manager names "t@school.org" as the teacher and also lists it as a student of the same class
- **THEN** the class is not saved and the manager is told why

#### Scenario: A refused save keeps what was typed
- **WHEN** a manager changes a class's name and teacher, presses save at the bottom of the form, and the save is refused
- **THEN** the reason is shown next to the save button and in view, the typed name and teacher are still in the form, and nothing was saved

### Requirement: Editing and deleting a class
A manager SHALL be able to change a class's name, students, teacher, AI switch and budget, and delete a class after confirming. Neither SHALL delete any student's progress.

#### Scenario: Deleting a class
- **WHEN** a manager deletes a class and confirms
- **THEN** the class is gone, and its students' progress is still there

### Requirement: Class and student lists
A manager SHALL see every class with its name, number of students and their emails and its teacher, and a list of all students with the classes each belongs to.

#### Scenario: A student in two classes
- **WHEN** a manager opens the students list and a student belongs to "ט'3" and "ט'4"
- **THEN** that student's row shows both classes

### Requirement: Teacher home
A teacher's home SHALL list the classes they teach, each with its students. A teacher MUST NOT be able to change a class's name, teacher, AI switch or budget.

#### Scenario: Two classes
- **WHEN** a teacher who teaches "ט'3" and "ט'4" signs in
- **THEN** their home lists both classes with their students

#### Scenario: No class yet
- **WHEN** a teacher who teaches no class signs in
- **THEN** their home says that a manager chooses who teaches each class

### Requirement: A student's lessons
A student who belongs to at least one class SHALL have every lesson of the bank, whatever lessons were stored for their classes before. A student in no class has none.

#### Scenario: Two classes, different lessons
- **WHEN** a student is in one class stored with lessons A and B and another stored with B and C
- **THEN** the student's lessons are every lesson of the bank

#### Scenario: A class saved with some lessons
- **WHEN** a student is in a class that was saved earlier with only lessons A and B
- **THEN** the student's path has every lesson

#### Scenario: No class
- **WHEN** a student who is in no class signs in
- **THEN** they see no lessons
