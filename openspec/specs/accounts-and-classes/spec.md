# accounts-and-classes Specification

## Purpose

Lets students and teachers sign in with their school Google accounts, and lets a teacher create classes and add students, so every other feature knows who the student is and which class they belong to.

## Requirements

### Requirement: Google sign-in
Students and teachers SHALL sign in with their Google account. The app MUST NOT show any student content before sign-in.

#### Scenario: Signing in
- **WHEN** a student opens the app and signs in with Google
- **THEN** they see the app as a student

#### Scenario: Not signed in
- **WHEN** someone opens the app without signing in
- **THEN** only the sign-in screen is shown

### Requirement: Teacher accounts
Only accounts listed as teachers in the app's settings SHALL get the teacher screens. Every other signed-in account SHALL be treated as a student.

#### Scenario: Listed teacher
- **WHEN** an account listed as a teacher signs in
- **THEN** they see the teacher screens

#### Scenario: Not listed
- **WHEN** an account not listed as a teacher signs in
- **THEN** they see no teacher screens

### Requirement: Teacher creates classes
A teacher SHALL be able to create a class with a name and see the classes they created.

#### Scenario: New class
- **WHEN** a teacher creates the class "ט'3"
- **THEN** "ט'3" appears in their list of classes

### Requirement: Teacher adds students by email
A teacher SHALL be able to add students to a class by their email addresses, one or many at once, and remove them. A student SHALL belong to one class at a time.

#### Scenario: Adding a list
- **WHEN** a teacher pastes 25 email addresses into class "ט'3"
- **THEN** the 25 students are listed in "ט'3"

#### Scenario: Student in another class
- **WHEN** a teacher adds a student who already belongs to another class
- **THEN** the teacher is told which class the student is in, and the student is not added twice

### Requirement: Student not in a class
A signed-in student who is in no class SHALL see a message asking them to ask their teacher to add them, showing the email they signed in with.

#### Scenario: Not added yet
- **WHEN** a student signs in before the teacher added their email
- **THEN** they see the message with their email, and no lessons

### Requirement: Fresh start
The new app SHALL start with no students, classes or progress. Nothing SHALL be imported from the current app.

#### Scenario: First teacher sign-in
- **WHEN** a teacher signs in to the new app for the first time
- **THEN** they have no classes, even if they had classes in the current app
