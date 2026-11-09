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
The sheet SHALL show one question: its text with formulas, its figure or graph if any, and its choices in a new random order each time it is shown, with "question n of N" and a row of N dots, one for each question of the round. A round SHALL be the skill's practice questions, at most 10, each shown once. A dot SHALL be filled for a right answer and marked "✗" for a wrong one, and empty for a question not yet answered.

#### Scenario: Same question again
- **WHEN** a question is shown a second time
- **THEN** its choices may be in a different order, and the server still grades by the bank's choice

#### Scenario: A skill with 30 questions
- **WHEN** a student opens a skill that has 30 questions in the bank
- **THEN** the sheet says "question n of 10" and shows 10 dots, and only the first 10 questions come up in the round

#### Scenario: Dots after a mistake
- **WHEN** a student answers the 1st question right and the 2nd wrongly
- **THEN** the first dot is filled, the second is marked wrong, and the sheet says "question 3 of 10"

### Requirement: A right answer
A right answer SHALL get a short celebration and the count of right answers in a row. After a short countdown the next question SHALL appear; the student can skip or cancel the countdown. After the last question of the round there is no countdown: the sheet offers the round's result.

#### Scenario: Countdown
- **WHEN** a student answers correctly
- **THEN** a countdown to the next question starts, and pressing "next" shows it at once

### Requirement: A wrong answer
A wrong answer SHALL be quiet and SHALL show the name and tip of the mistake attached to the chosen choice, about the mistake and not the student. The chosen choice SHALL be marked as wrong with a symbol and a word on the choice itself ("✗ לא נכון"), not by colour alone, and no other choice SHALL be marked. It MUST NOT reveal the correct answer, and the question MUST NOT come back in the same round. The sheet SHALL offer "לשאלה הבאה" (after the last question: the round's result). When the mistake names a skill to go back to, the feedback SHALL link to it.

#### Scenario: Sign mistake
- **WHEN** a student picks a choice tagged with "טעות סימן באיבר האמצעי"
- **THEN** the mistake's name and tip are shown and no choice is marked as correct

#### Scenario: The chosen choice is marked
- **WHEN** a student picks a wrong choice
- **THEN** that choice shows "✗ לא נכון" and a stronger border, and every other choice looks as it did

#### Scenario: A wrong question does not return
- **WHEN** a student answers the 3rd question wrongly
- **THEN** it is not shown again in the round, and the round ends after the 10th question

### Requirement: A different next question
After any answer the next question SHALL be a question of the round that was not answered yet, picked at random. When every question of the round was answered, there is no next question and the sheet shows the round's result. A skill with one question has a round of one question.

#### Scenario: After a mistake
- **WHEN** a student answers a question wrongly
- **THEN** the next question is not the one just answered

#### Scenario: Never twice in a round
- **WHEN** a student answers all 10 questions of a skill
- **THEN** each question was shown exactly once, and none came back

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

### Requirement: A round's result
After the last answer of a round the sheet SHALL show how many questions were answered right out of the round's questions ("N מתוך 10") and, for each wrong answer, the question, the mistake's name and tip and a link to the skill to go back to when the bank names one. It MUST NOT show the correct answers. The result SHALL be shown again after leaving and returning, until a new round is started.

#### Scenario: Result
- **WHEN** a student answers the 10th question of a round with 7 right
- **THEN** the sheet shows "7 מתוך 10" and the three mistakes with their names and tips

#### Scenario: Leaving in the middle
- **WHEN** a student leaves after the 4th question and comes back
- **THEN** the round continues with the 5th question, and the dots show the first four answers

### Requirement: A new round
The result SHALL offer "סבב חדש", which starts a new round with all the skill's practice questions again in a new random order, and a way back to the path. Mastery SHALL be counted across rounds as before.

#### Scenario: Another round
- **WHEN** a student presses "סבב חדש" after a finished round
- **THEN** a round of the 10 questions starts again, with empty dots

#### Scenario: Coming back after a finished round
- **WHEN** a student leaves after finishing a round and opens the skill again
- **THEN** the result is shown, and "סבב חדש" starts a round of the 10 questions again

### Requirement: Thinking indicator
As soon as a choice is tapped, the sheet SHALL show that the answer is being checked: the tapped choice shows a spinner, a status line says "בודקים…", and the other choices are dimmed and cannot be tapped. The indicator SHALL go away when the answer arrives or fails, and it MUST NOT depend on motion: with reduced motion the words are shown and the spinner is still.

#### Scenario: A slow answer
- **WHEN** a student taps a choice and the server takes two seconds
- **THEN** during those two seconds the tapped choice shows a spinner, "בודקים…" is shown and the other choices cannot be tapped, and the result replaces them when it arrives

#### Scenario: An error
- **WHEN** the answer cannot be sent
- **THEN** the indicator goes away, the choices can be tapped again and the error is shown
