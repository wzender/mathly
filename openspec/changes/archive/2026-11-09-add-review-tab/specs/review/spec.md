## ADDED Requirements

### Requirement: Wrong answers go to חזרה
Every wrong answer SHALL be added to the student's חזרה list: in path practice, in a lesson בוחן, in a practice test and in the simulation. A question left unanswered when a בוחן or a test is submitted or its time ends SHALL be added as well. A question already in the list SHALL not be added again.

#### Scenario: A wrong practice answer
- **WHEN** a student answers a practice question wrongly
- **THEN** the question is in their חזרה list

#### Scenario: A בוחן
- **WHEN** a student submits a בוחן with two wrong answers and one unanswered question
- **THEN** all three questions are in their חזרה list

#### Scenario: Twice
- **WHEN** a student gets the same question wrong again
- **THEN** it is in the list once

### Requirement: The חזרה tab
The student's tab bar SHALL have a "חזרה" tab. It SHALL show how many questions wait, and one question at a time with its choices, the oldest first, never the one just answered when others wait. An empty list SHALL say so. The tab MUST be reachable on a phone without sideways scrolling.

#### Scenario: Questions waiting
- **WHEN** a student with five questions in the list opens חזרה
- **THEN** it says five wait and shows the oldest question

#### Scenario: Empty
- **WHEN** the list is empty
- **THEN** the tab says there is nothing to review

### Requirement: Redoing a question
A right answer in חזרה SHALL remove the question from the list. A wrong answer SHALL keep it, name the mistake and show its tip, and MUST NOT show the right choice. The right choice MUST NOT be sent to the page before the answer.

#### Scenario: Right
- **WHEN** a student answers a question in חזרה correctly
- **THEN** it leaves the list and the count goes down by one

#### Scenario: Wrong
- **WHEN** they answer it wrongly
- **THEN** it stays, the mistake's name and tip show, and the right choice is not shown

### Requirement: Practice only
Redoing a question in חזרה SHALL NOT change any skill's mastery, any grade or the readiness meter, and SHALL NOT change which questions a practice round has left. Each right answer SHALL count toward the daily goal.

#### Scenario: Mastery
- **WHEN** a student answers ten questions right in חזרה on a skill they have not mastered
- **THEN** the skill is not mastered because of them

#### Scenario: The daily goal
- **WHEN** a student answers a question right in חזרה
- **THEN** today's correct answers go up by one
