# Spec Delta

## Purpose

Separates unit quizzes a student may retake for practice from final unit quizzes the teacher gives once for an official grade, and says which grade counts and how a student prepares for a retake.

## ADDED Requirements

### Requirement: Every sitting has a mode
Each unit-quiz sitting SHALL be either a practice sitting or a final sitting, fixed when the sitting starts. Sittings stored before this change SHALL be practice sittings.

#### Scenario: Old sitting
- **WHEN** this change is deployed and a student has a sitting of unit `t` from last week
- **THEN** that sitting is a practice sitting, with its grade unchanged

### Requirement: Practice quizzes can be retaken
A student SHALL be able to start a practice sitting of any unit quiz open to their class at any time, any number of times, except while a final sitting of the same unit is open to them and not yet handed in.

#### Scenario: Third practice sitting
- **WHEN** a student has handed in two practice sittings of unit `t`
- **THEN** they can start a third practice sitting

#### Scenario: Final quiz open
- **WHEN** a final quiz of unit `t` is open to the student and they have not handed it in
- **THEN** the practice quiz of unit `t` cannot be started, and the intro says the final quiz is open

### Requirement: Teacher opens a final quiz
The class teacher or a manager SHALL be able to open a final quiz of a class unit for the class, with a start time and an end time. A student SHALL be able to start the final sitting only between them. One window per unit and class SHALL be open at a time. Any other account MUST be refused.

#### Scenario: Window opened
- **WHEN** the teacher of 9א opens the final quiz of unit `g` from 10/11 08:00 to 10/11 09:30
- **THEN** students of 9א see it in their task list, and can start it from 08:00

#### Scenario: Before the window
- **WHEN** a student tries to start the final sitting at 07:55
- **THEN** the server refuses, and the intro shows when it opens

#### Scenario: Not the class teacher
- **WHEN** a teacher of another class tries to open a final quiz for 9א
- **THEN** the server refuses with a forbidden error

### Requirement: One final sitting per student
A student SHALL have at most one final sitting per window, unless the teacher granted them another one. Starting it SHALL be confirmed by the student after a notice that it cannot be retaken.

#### Scenario: Second start refused
- **WHEN** a student who handed in the final sitting of unit `g` tries to start another one in the same window
- **THEN** the server refuses, and the intro shows the handed-in sitting

#### Scenario: Confirmation
- **WHEN** a student presses "התחלת הבוחן הסופי"
- **THEN** the app asks them to confirm that the quiz is given once, before the clock starts

### Requirement: The server keeps the final quiz clock
The server SHALL record when a final sitting starts and SHALL accept its answers until the quiz's minutes plus the photo grace time have passed, or until the window ends, whichever is first. Answers sent after that MUST be rejected; the sitting SHALL be handed in with the answers stored by then.

#### Scenario: Closed after time
- **WHEN** a student started a 45-minute final sitting at 08:00 and sends a photo at 09:00, after the 10-minute grace time
- **THEN** the server rejects the photo, and the sitting is handed in with the answers it had

#### Scenario: Page reloaded
- **WHEN** the student reloads the page during the sitting
- **THEN** the clock shows the time left from the server's start time

### Requirement: Teacher grants another final sitting
The class teacher SHALL be able to grant a student one more final sitting of a unit, with an optional reason of up to 200 characters, also after the window ended. The extra sitting SHALL have its own end time set by the teacher.

#### Scenario: Absent student
- **WHEN** a student was absent on 10/11 and the teacher grants them a final sitting of unit `g` until 13/11
- **THEN** the student can start it until 13/11, and the report shows it was granted, with the reason

### Requirement: Which grade counts
The official grade of a unit for a student SHALL be the grade of their latest handed-in final sitting of that unit. Practice sittings MUST NOT change the official grade. A unit with no final sitting SHALL have no official grade.

#### Scenario: Practice after the final
- **WHEN** a student got 62 in the final sitting of `g` and 90 in a practice sitting afterwards
- **THEN** the official grade of `g` stays 62, and the practice grade is shown as practice

#### Scenario: Granted second final
- **WHEN** the teacher granted a second final sitting and the student got 75 in it
- **THEN** the official grade becomes 75, and the first final sitting stays visible in the history

### Requirement: Final results follow the teacher's release
Grades and solutions of a final quiz SHALL be shown to students only after the teacher releases the results for the window. Before that, the student SHALL see that the sitting was handed in and is waiting for results.

#### Scenario: Before release
- **WHEN** all answers of a student's final sitting are checked but the teacher has not released results
- **THEN** the student sees "הוגש · התוצאות יפורסמו על ידי המורה" and no grade

#### Scenario: Released
- **WHEN** the teacher releases the results of the window
- **THEN** every student of the window sees their grade, the feedback and the solutions

### Requirement: Practise before a retake
After a practice sitting with questions that lost points, the result screen SHALL list the skills tagged on those questions with each skill's state for the student, and offer to practise them before a retake. The student SHALL be able to retake without practising.

#### Scenario: Points lost on two questions
- **WHEN** a student lost points on questions tagged `g_pyth` and `g_pyth_word`
- **THEN** the result lists both skills with buttons to practise them, and a "ניסיון נוסף" button

#### Scenario: Full marks
- **WHEN** the student got 100 in a practice sitting
- **THEN** no skills are suggested
