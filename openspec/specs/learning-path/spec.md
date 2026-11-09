# learning-path Specification

## Purpose
The student's main screen: every lesson of their classes as a hub with its skills as stars, joined in one trail, so they always see where they stand and where to continue.

## Requirements

### Requirement: Choosing a subject
After sign-in a student SHALL first see the subjects of their classes as cards, each with its name and a bar "N מתוך M מיומנויות". Math is the only subject, and its card is named "מתמטיקה כיתה ט - מצוינות". Tapping a card SHALL open the subject's home, reached by the tab bar, and every screen of the subject SHALL have a way back to the subjects.

#### Scenario: After signing in
- **WHEN** a student signs in
- **THEN** they see a card "מתמטיקה כיתה ט - מצוינות" with "N מתוך M מיומנויות", and no path yet

#### Scenario: Opening the subject
- **WHEN** the student taps the math card
- **THEN** the math home opens, with the tab bar and a way back to the subjects

#### Scenario: A link to a skill
- **WHEN** a student opens `#/skill/<id>` directly or reloads the page on it
- **THEN** the math path opens with that skill's exercise screen over it

### Requirement: Trail of lesson hubs
Every lesson of the student's classes SHALL be a hub showing its name and "mastered of total", with its skills in a ring around it, in order, numbered from the top and clockwise. The hubs SHALL be joined by a vertical trail from a start marker with the owl to an end marker.

#### Scenario: Opening the path
- **WHEN** a student opens the path
- **THEN** each of their lessons is a hub with its numbered skills around it, on one trail

### Requirement: Stars show state in words
Each skill SHALL be a star whose look shows its state, with a symbol and word under it: "○ לא התחלת", "◐ בלמידה" or "✓ נשלטה". A mastered star SHALL look clearly different from the other two.

#### Scenario: Three states
- **WHEN** a lesson has a mastered, a learning and a not-started skill
- **THEN** their stars show "✓ נשלטה", "◐ בלמידה" and "○ לא התחלת"

### Requirement: Next skill
One skill SHALL carry the owl as the suggested next: the unmastered skill answered most recently, else the first unmastered skill in the bank's order. When all are mastered none is marked. The marker MUST NOT lock, hide or reorder anything.

#### Scenario: New student
- **WHEN** a student who answered nothing opens the path
- **THEN** the owl is on the first skill of the first lesson and every skill can be opened

#### Scenario: Continuing
- **WHEN** a student's last answer was on an unmastered skill
- **THEN** the owl is on that skill

### Requirement: All open
The student SHALL be able to open any lesson and any skill in it at any time, in any order.

#### Scenario: Jumping ahead
- **WHEN** a student opens a skill in the last lesson first
- **THEN** its exercise screen opens

### Requirement: Opening a skill from the path
Tapping a star SHALL open its exercise screen over the path; closing it SHALL show the path with the star updated. The path SHALL open scrolled to the next skill.

#### Scenario: Back from practice
- **WHEN** a student masters a skill and closes the sheet
- **THEN** its star on the path shows "✓ נשלטה"

### Requirement: Accessible stars
Each star SHALL be a control whose accessible name is its number, the skill's name and its state in words, reachable and opened from the keyboard.

#### Scenario: Keyboard
- **WHEN** a student moves to a star with Tab and presses Enter
- **THEN** its exercise screen opens

### Requirement: Fits a phone
The path SHALL fit a 360px-wide screen without sideways scrolling, including the lesson with the most skills.

#### Scenario: Six skills
- **WHEN** the lesson with six skills is shown on a 360px screen
- **THEN** all six stars and their words are visible without sideways scrolling

### Requirement: A completed lesson
A lesson SHALL be completed when every one of its skills is mastered, or when its quiz was passed. Passing the quiz MUST NOT change any skill's state. A completed lesson SHALL be marked on its hub with the word "הושלם".

#### Scenario: By skills
- **WHEN** a student has mastered all five skills of a lesson
- **THEN** the lesson is marked completed

#### Scenario: By the quiz
- **WHEN** a student passes a lesson's quiz while two of its skills are still in learning
- **THEN** the lesson is marked completed, and the two skills are still in learning

#### Scenario: Neither
- **WHEN** a student has mastered four of five skills and has not passed the quiz
- **THEN** the lesson is not completed

### Requirement: Lessons behind the curriculum
A lesson that has a date in the curriculum, whose date has passed and that is not completed SHALL be marked on the path as behind, with a marker and its date in words ("היה אמור להסתיים ב־3.11"). The path SHALL say how many lessons are behind. A lesson with no date, a date still ahead, or a completed lesson MUST NOT be marked. Nothing SHALL be locked.

#### Scenario: Behind
- **WHEN** a lesson's date was yesterday and the student has not completed it
- **THEN** its hub shows the behind marker and the date, and the path says "1 שיעורים בפיגור"

#### Scenario: Completed in time
- **WHEN** a lesson's date has passed and the student passed its quiz
- **THEN** the lesson is marked completed and not behind

#### Scenario: Date still ahead or none
- **WHEN** a lesson's date is next week, or it has none
- **THEN** it is not marked behind
