# Spec Delta

## Purpose

Splits the student's screen into a home tab that shows only what has a date or needs action, and a path tab for self-paced learning, so a student sees at a glance what matters today.

## ADDED Requirements

### Requirement: Student has a home tab and a path tab
A signed-in student SHALL have a "בית" tab and a "מסלול" tab, next to the existing collection tab. The app SHALL open on "בית". A teacher looking at the app as a student SHALL see the same tabs.

#### Scenario: Opening the app
- **WHEN** a student opens the math app
- **THEN** the "בית" tab is selected, and "מסלול" and "האוסף" are offered in the tab bar

#### Scenario: Teacher preview
- **WHEN** a teacher opens the student preview
- **THEN** the preview shows the "בית" and "מסלול" tabs as a student sees them

### Requirement: Home shows only dated or actionable items
The home tab SHALL show, in this order: the next exam on the student's class exam table, up to 3 quizzes, the work that is due (the task summary and open assignments), and teacher comments the student has not seen. It MUST NOT show the trail of units, the daily goal card, spaced review or the recurring-mistakes card.

#### Scenario: Busy week
- **WHEN** a student has a math exam in 5 days, an assignment due tomorrow and one new teacher comment
- **THEN** home shows the exam countdown, then the quizzes, then the assignment, then the comment, and no trail

#### Scenario: Comments already seen
- **WHEN** every teacher comment was already opened by the student
- **THEN** home shows no comments card

### Requirement: Home links to the next exam
The exam item SHALL show the subject, the date and the days left. When the exam names units, it SHALL open the exam's preparation view. Only the nearest upcoming exam SHALL be shown on home.

#### Scenario: Exam with units
- **WHEN** the nearest exam is math on 15/11, naming units, and today is 06/11
- **THEN** home shows "מבחן במתמטיקה · עוד 9 ימים", and tapping it opens the preparation view

#### Scenario: Exam without units
- **WHEN** the nearest exam names no units
- **THEN** home shows its subject, date and days left, without a link to a preparation view

### Requirement: Home is never empty
Home SHALL always end with a button that continues the path at the student's next topic. When nothing else is shown, home SHALL say there is nothing due now, above that button.

#### Scenario: Nothing due
- **WHEN** a student has no exam ahead, no open work, no new comments and no quiz offered
- **THEN** home says there is nothing due now and shows the "continue the path" button

#### Scenario: Continue
- **WHEN** the student presses "continue the path"
- **THEN** the path tab opens, scrolled to their next topic

### Requirement: Path tab holds self-paced learning
The path tab SHALL show the daily goal and streak, spaced review, the recurring-mistakes card and the trail of units, in that order. Everything that was on the student's old home screen and is not on the new home SHALL be on the path tab.

#### Scenario: Review due
- **WHEN** a student has 3 topics due for spaced review
- **THEN** the review card is shown on the path tab, not on home

#### Scenario: Jump to a unit
- **WHEN** a student taps a constellation in the collection tab
- **THEN** the path tab opens, scrolled to that unit

### Requirement: Teacher home is unchanged
A class teacher who is not in student preview SHALL keep their current home (their classes) and SHALL NOT get a path tab.

#### Scenario: Teacher opens the app
- **WHEN** a class teacher opens the math app
- **THEN** they see their classes as before, and the tab bar has no "מסלול" tab
