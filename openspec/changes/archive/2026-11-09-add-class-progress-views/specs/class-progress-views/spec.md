## ADDED Requirements

### Requirement: The progress tab
A teacher's screen SHALL have a "התקדמות" tab, with the number of students of the teacher's classes like the other tabs, and each class card SHALL have a "התקדמות" shortcut to it. The tab SHALL show one class at a time, with a way to choose the class when the teacher has several. Only a class's own teacher or a developer SHALL be able to read its progress. A manager or an admin MUST NOT, and a teacher MUST NOT read another teacher's class.

#### Scenario: Two classes
- **WHEN** a teacher of two classes opens the tab
- **THEN** they see the first class and can switch to the other

#### Scenario: Another teacher's class
- **WHEN** a teacher asks for the progress of a class they do not teach, or a manager asks for any class
- **THEN** the server refuses

#### Scenario: A developer
- **WHEN** a developer opens any class's progress
- **THEN** they see it as the class's teacher would

### Requirement: Progress by lesson
The progress view SHALL list the students in rows and the lessons in columns, never the skills. Each cell SHALL show only three things: a progress bar with the percent of the lesson's skills mastered written on it, the best quiz grade as a bare number (a dash for none, without the word "בוחן"), and, in the current period, a warning mark when the lesson is behind the curriculum and not completed. The cell's accessible name SHALL still say the state in words (הושלם, בלמידה, לא התחילו, בפיגור).

#### Scenario: Cell contents
- **WHEN** a student has mastered 3 of 5 skills of a lesson and their best quiz grade is 80
- **THEN** the cell shows a bar with 60% and the number 80, and nothing else

#### Scenario: Behind
- **WHEN** a lesson's date has passed and a student has neither mastered all its skills nor passed its quiz
- **THEN** that student's cell for the lesson carries the warning mark

#### Scenario: Completed or not started
- **WHEN** a student has passed a lesson's quiz, or has done nothing in it
- **THEN** the cell's accessible name says "הושלם" or "לא התחילו", and the cell shows no extra text

#### Scenario: No skill columns
- **WHEN** a teacher opens the progress view
- **THEN** no column or cell stands for a single skill

### Requirement: The progress table
A student who has not signed in yet SHALL have every lesson not started. The table SHALL scroll inside its own frame with the student column fixed, and the page MUST NOT scroll sideways.

#### Scenario: Not signed in yet
- **WHEN** a student was added to the class and has never signed in
- **THEN** their row shows every lesson as not started

#### Scenario: A phone
- **WHEN** the table is wider than the screen
- **THEN** it scrolls inside its frame and the page does not scroll sideways

### Requirement: Periods
The progress by lesson SHALL have two period tabs, "ספט׳–דצמ׳" and "ינו׳–יוני". A period SHALL show the lessons of that period, by the lesson's date in the curriculum or, when it has none, by the last month of the bank's month for it, and the states as they were at the end of the period, or today for the current period. The current period SHALL be open first.

#### Scenario: A past period
- **WHEN** a skill was mastered on 20 January and the teacher opens the progress view in March
- **THEN** that lesson's percent does not include the skill in the first period's view (which ends on 31 December), and does in the second

#### Scenario: Lessons of the period
- **WHEN** a lesson is dated 15 February
- **THEN** it appears in the second period and not in the first

### Requirement: Readiness per student
For the class's nearest coming test the tab SHALL list each student's readiness number and its word, their mastery percent, their practice-test average and their simulation grade, with a dash for what they have not done. A class with no coming test SHALL say so.

#### Scenario: A coming test
- **WHEN** a class has a test in ten days and one student has done nothing
- **THEN** the table lists that student with a dash for what is missing

#### Scenario: No test
- **WHEN** the class has no coming test
- **THEN** the readiness view says no test is set
