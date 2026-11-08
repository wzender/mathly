# exercise-screen Specification

## Purpose
The screen where a student practices one skill with the exercise bank's questions: instant feedback that teaches from the mistake, help when stuck, and the board to work things out.

## Requirements

### Requirement: Layout
The exercise screen SHALL open as a sheet over the path. Its header SHALL show the lesson's name, the skill's name, a completed mark when the skill is mastered, a board button, a "?" help button and a close button, with the skill's short explanation under it.

#### Scenario: Opening a skill
- **WHEN** a student opens the skill "פירוק טרינום"
- **THEN** the sheet shows the lesson's name, "פירוק טרינום", the board, "?" and close buttons, and the explanation

### Requirement: One question at a time
The sheet SHALL show one question: its text with formulas, its figure or graph if any, and its choices in a new random order each time it is shown, with "question n of N" and a row of dots for the skill's questions.

#### Scenario: Same question again
- **WHEN** a question is shown a second time
- **THEN** its choices may be in a different order, and the server still grades by the bank's choice

### Requirement: A right answer
A right answer SHALL get a short celebration and the count of right answers in a row. After a short countdown the next question SHALL appear; the student can skip or cancel the countdown.

#### Scenario: Countdown
- **WHEN** a student answers correctly
- **THEN** a countdown to the next question starts, and pressing "next" shows it at once

### Requirement: A wrong answer
A wrong answer SHALL be quiet and SHALL show the name and tip of the mistake attached to the chosen choice, about the mistake and not the student. It MUST NOT reveal the correct answer. When the mistake names a skill to go back to, the feedback SHALL link to it.

#### Scenario: Sign mistake
- **WHEN** a student picks a choice tagged with "טעות סימן באיבר האמצעי"
- **THEN** the mistake's name and tip are shown and no choice is marked as correct

### Requirement: A different next question
After any answer the next question SHALL be another question of the same skill, picked at random among those this student has seen least, never the one just answered. A skill with one question repeats it.

#### Scenario: After a mistake
- **WHEN** a student answers a question wrongly
- **THEN** the next question is not the one just answered

### Requirement: Help
The "?" button SHALL show the skill's explanation and, where the bank has one, a solved example. Opening it SHALL make the answer to the question on screen not count for mastery; that answer still counts for the daily goal.

#### Scenario: Help opened
- **WHEN** a student opens "?" and then answers correctly
- **THEN** the answer is stored as given with help and does not count toward mastery

### Requirement: Related skills
The sheet SHALL show the skills this one requires and the skills it opens as tappable chips, which open those skills and never lock anything.

#### Scenario: Required skill
- **WHEN** a student taps a "requires" chip
- **THEN** that skill's exercise screen opens

### Requirement: Resuming
Reopening a skill SHALL continue with the question that was on screen, and an answer to a question that is no longer on screen SHALL be refused.

#### Scenario: Two tabs
- **WHEN** a student answers in one tab a question that another tab already replaced
- **THEN** the answer is refused and the screen shows the current question

### Requirement: Skill without questions
A skill with no questions SHALL say there is no practice for it yet, and cannot be mastered.

#### Scenario: Empty skill
- **WHEN** a student opens a skill with no questions
- **THEN** the sheet says there is no practice yet
