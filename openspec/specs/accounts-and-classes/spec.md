# accounts-and-classes Specification

## Purpose

Lets students and teachers sign in with their school Google accounts, and lets a teacher create classes and add students, so every other feature knows who the student is and which class they belong to.

## Requirements

### Requirement: Google sign-in
Students, teachers, managers, admins and developers SHALL sign in with their Google account. Before sign-in the only screen SHALL be the sign-in page: the animated logo "לומדים בכיף" (from mathly1) and the owl mascot, one line of status text and one button "כניסה עם Google". The app MUST NOT show or serve any student content, class or progress before sign-in. The session SHALL stay on the device, and sign-out SHALL be available on every screen.

#### Scenario: Signing in
- **WHEN** a student opens the app and signs in with Google
- **THEN** they see the app as a student

#### Scenario: Not signed in
- **WHEN** someone opens the app without signing in
- **THEN** only the sign-in page is shown

#### Scenario: Coming back the next day
- **WHEN** a signed-in student closes the app and opens it the next day on the same device
- **THEN** they are still signed in

### Requirement: Teacher adds students by email
The teacher of a class, and a manager, SHALL be able to add students to that class by pasting email addresses (one per line; commas and spaces also separate them) and to remove them. Repeated addresses SHALL be ignored and invalid ones reported. A student MAY belong to more than one class. Removing a student SHALL NOT delete their progress.

#### Scenario: Adding a list
- **WHEN** the teacher of "ט'3" pastes 25 email addresses into the class
- **THEN** the 25 students are listed in "ט'3"

#### Scenario: Student in another class
- **WHEN** a teacher adds a student who already belongs to another class
- **THEN** the student is added, and now belongs to both classes

#### Scenario: Invalid address
- **WHEN** the pasted text contains "dana@" among valid addresses
- **THEN** the valid ones are added and "dana@" is reported as invalid

#### Scenario: The teacher in the list
- **WHEN** the teacher of "ט'3" pastes their own address among others
- **THEN** their own address is reported as not allowed, and the others are added

### Requirement: Student not in a class
A signed-in student who is in no class SHALL see a message asking them to ask their teacher or a manager to add them, showing the email they signed in with, and nothing else.

#### Scenario: Not added yet
- **WHEN** a student signs in before a teacher or manager added their email
- **THEN** they see the message with their email, and no lessons

### Requirement: Fresh start
The new app SHALL start with no students, classes or progress. Nothing SHALL be imported from the current app.

#### Scenario: First teacher sign-in
- **WHEN** a teacher signs in to the new app for the first time
- **THEN** they have no classes, even if they had classes in the current app

### Requirement: Five roles
The app SHALL have five roles: student, teacher, manager, admin and developer. The server SHALL decide a signed-in email's roles on every request: developer when the email is in the developer setting; teacher when it is in the teacher setting, is a class's teacher, or was given the role; manager or admin when given the role; student otherwise. A person MAY hold several roles and gets the screens of each.

#### Scenario: Class teacher
- **WHEN** an email that is in no setting is named as the teacher of a class and signs in
- **THEN** it gets the teacher screens for that class

#### Scenario: Several roles
- **WHEN** a person has both the manager and the teacher role
- **THEN** they can reach both the classes screen and their teacher home

### Requirement: Permissions per role
Each role SHALL be limited to: student, their own path and data; teacher, the data of the students of the classes they teach and those classes' rosters; manager, classes and their AI settings with no learning data; admin, roles of accounts with no learning data; developer, everything. The server SHALL refuse any request outside the caller's permissions.

#### Scenario: Teacher of another class
- **WHEN** a teacher asks for the progress of a student who is not in a class they teach
- **THEN** the server refuses

#### Scenario: Manager and learning data
- **WHEN** a manager asks for a student's answers or grades
- **THEN** the server refuses

### Requirement: Admin gives roles
An admin SHALL see the accounts the app knows and give or take away the roles student, teacher, manager and admin. Roles SHALL belong to an email address, so a role can be given before the person's first sign-in. The developer role MUST NOT be given here. The last admin MUST NOT be able to take away their own admin role.

#### Scenario: Role before first sign-in
- **WHEN** an admin gives "rina@school.org" the manager role and Rina signs in for the first time a day later
- **THEN** Rina gets the manager screens

#### Scenario: Last admin
- **WHEN** the only admin tries to remove their own admin role
- **THEN** the change is refused with a message

#### Scenario: A change shows soon
- **WHEN** an admin takes the manager role from someone who is signed in
- **THEN** within 30 seconds that person no longer has the manager screens

### Requirement: The first admins
The app's settings SHALL be able to name admin emails, so a new installation has an admin before anyone gives roles.

#### Scenario: Empty installation
- **WHEN** the app starts with no roles stored and the settings name "head@school.org" as an admin
- **THEN** "head@school.org" gets the admin screens at sign-in

### Requirement: Role switcher
A person with more than one role SHALL get a chip for each role in the header, each opening that role's home; a developer SHALL get all five. A person with one role SHALL see no chips. The last role chosen SHALL be remembered on the device. A link or a reload SHALL land on the screen it points to, and switching role SHALL clear the address.

#### Scenario: Two roles
- **WHEN** a person who is a manager and a teacher signs in
- **THEN** the header has a chip for each, and the one they used last opens first

#### Scenario: A link
- **WHEN** a student opens the app through a link to their collection
- **THEN** after signing in they see their collection, and reloading shows it again

#### Scenario: Switching clears the address
- **WHEN** a person with two roles switches from one to the other
- **THEN** the address no longer carries the first role's screen

### Requirement: Own access
Every signed-in account SHALL be able to see its own roles and what they allow.

#### Scenario: Checking own roles
- **WHEN** a teacher opens the page of their own access
- **THEN** it lists the teacher role and what it allows

### Requirement: Manager creates classes
A manager (or a developer) SHALL create, edit and delete classes. A class SHALL have a name (1–80 characters, unique ignoring case), the lessons it studies (at least one, from the bank), its students, at most one teacher (an email, never also a student of that class), an AI switch that starts off, and a daily AI budget (default 150).

#### Scenario: New class
- **WHEN** a manager creates "ט'3" with two lessons, a teacher and 25 students
- **THEN** "ט'3" appears in the class list with those lessons, that teacher and 25 students, and its AI switch is off

#### Scenario: Teacher listed as a student
- **WHEN** a manager names "t@school.org" as the teacher and also lists it as a student of the same class
- **THEN** the class is not saved and the manager is told why

#### Scenario: A refused save keeps what was typed
- **WHEN** a manager changes a class's name and teacher, presses save at the bottom of the form, and the save is refused
- **THEN** the reason is shown next to the save button and in view, the typed name and teacher are still in the form, and nothing was saved

### Requirement: Editing and deleting a class
A manager SHALL be able to change a class's name, lessons, students, teacher, AI switch and budget, and delete a class after confirming. Neither SHALL delete any student's progress.

#### Scenario: Deleting a class
- **WHEN** a manager deletes a class and confirms
- **THEN** the class is gone, and its students' progress is still there

### Requirement: Class and student lists
A manager SHALL see every class with its name, lessons, number of students and their emails and its teacher, and a list of all students with the classes each belongs to.

#### Scenario: A student in two classes
- **WHEN** a manager opens the students list and a student belongs to "ט'3" and "ט'4"
- **THEN** that student's row shows both classes

### Requirement: Teacher home
A teacher's home SHALL list the classes they teach, each with its students. A teacher MUST NOT be able to change a class's name, lessons, teacher, AI switch or budget.

#### Scenario: Two classes
- **WHEN** a teacher who teaches "ט'3" and "ט'4" signs in
- **THEN** their home lists both classes with their students

#### Scenario: No class yet
- **WHEN** a teacher who teaches no class signs in
- **THEN** their home says that a manager chooses who teaches each class

### Requirement: A student's lessons
A student's lessons SHALL be the lessons of all the classes they belong to.

#### Scenario: Two classes, different lessons
- **WHEN** a student is in one class studying lessons A and B and another studying B and C
- **THEN** the student's lessons are A, B and C

### Requirement: First sign-in links the account
The first time a person signs in, their account SHALL be linked to the class entries and roles stored for their email.

#### Scenario: Added before signing in
- **WHEN** a manager adds "noa@school.org" to "ט'3" and Noa signs in for the first time
- **THEN** Noa is a student of "ט'3"

### Requirement: Sign-in problems are explained
When the sign-in service cannot be reached the sign-in page SHALL say so and offer to try again. When a session has expired the person SHALL return to the sign-in page with a short message.

#### Scenario: Service down
- **WHEN** the sign-in service does not answer
- **THEN** the sign-in page says it could not connect and shows a "try again" button

### Requirement: Every request is checked
The server SHALL check the sign-in and the caller's permissions on every request except the health check.

#### Scenario: No sign-in
- **WHEN** any request other than the health check arrives without a valid sign-in
- **THEN** the server refuses it
