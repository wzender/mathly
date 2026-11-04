# Spec Delta

## Purpose

Lets the class teacher correct and comment on the automatic check of a student's open answer, lets the student ask for that, and makes the teacher's word the one that counts.

## ADDED Requirements

### Requirement: Teacher opens a student's checked answer
The class teacher of a student's class, or a manager, SHALL be able to open any of that student's open answers that have a saved photo: the question, the photo, and every completed automatic check with its transcription, verdict, score and feedback. Any other account MUST be refused.

#### Scenario: Class teacher opens an answer
- **WHEN** the teacher of class 9א opens a unit-quiz answer of a student in 9א from the class report
- **THEN** they see the question, the student's photo and the AI check

#### Scenario: Teacher of another class
- **WHEN** a teacher who does not teach any class the student is in asks for the answer
- **THEN** the server refuses with a forbidden error and sends neither the image nor the check

### Requirement: Teacher saves a review with score and comment
The teacher SHALL be able to save a review on an answer with a teacher score from 0 to 100, a comment of up to 1000 characters, or both. A review with neither MUST be rejected. A new review SHALL replace the teacher's previous one for that answer, and the time and reviewer SHALL be recorded.

#### Scenario: Teacher corrects the AI score
- **WHEN** the AI gave 40 and the teacher saves a score of 85 with the comment "הדרך נכונה, טעות חישוב בשורה 3"
- **THEN** the answer's effective score is 85 and the comment is stored with the teacher's email and the time

#### Scenario: Teacher grades an unreadable answer
- **WHEN** the AI marked an answer unreadable and the teacher saves a score of 70
- **THEN** the answer has an effective score of 70

#### Scenario: Empty review
- **WHEN** the teacher saves a review with no score and no comment
- **THEN** the server rejects it and nothing changes

#### Scenario: Score out of range
- **WHEN** the teacher sends a score of 120
- **THEN** the server rejects it

### Requirement: Teacher score takes precedence in grades
Wherever an answer's score is used (unit-quiz grade, skill completion), the teacher score SHALL be used when the answer has one, otherwise the AI score.

#### Scenario: Quiz grade with a teacher score
- **WHEN** a sitting's question worth 25 points has an AI score of 40 and a teacher score of 80
- **THEN** that question contributes 20 points to the sitting's grade

#### Scenario: Skill completed by the teacher
- **WHEN** the teacher gives a score of 100 to an open skill answer the AI marked partial
- **THEN** the skill is completed for the student the next time their page reads that answer

### Requirement: Student sees the teacher's review
The student SHALL see the teacher's comment and score on the answer, marked as from their teacher and shown before the AI feedback. The AI's own score SHALL stay visible, labelled as the automatic check.

#### Scenario: Student opens a reviewed answer
- **WHEN** the student opens a quiz result whose second answer has a teacher review
- **THEN** the second answer shows "הערת המורה" with the comment and the teacher score, followed by the AI check with its score

### Requirement: Student asks the teacher to look again
The student SHALL be able to ask their class teacher to look again at a checked answer, with an optional message of up to 300 characters. At most one open request SHALL exist per answer. The request SHALL close when the teacher saves a review on that answer.

#### Scenario: Student disputes a check
- **WHEN** the student presses "לבקש מהמורה לבדוק שוב" with the message "כתבתי x=4, לא x=1"
- **THEN** the request appears in the teacher's list of requests to look again with the student, the question and the message

#### Scenario: Second request on the same answer
- **WHEN** the student asks again while their first request on that answer is open
- **THEN** no second request is created and the student sees that the request is already waiting

#### Scenario: Teacher answers the request
- **WHEN** the teacher saves a review on that answer
- **THEN** the request closes and disappears from the teacher's list

### Requirement: Student is told about new teacher comments
The student's home screen SHALL show a notice when a teacher has saved a review on one of their answers that they have not opened since, linking to that answer.

#### Scenario: New comment
- **WHEN** the teacher reviewed one of the student's answers yesterday and the student has not opened it
- **THEN** the home screen shows a notice that the teacher commented, and opening it shows the answer

#### Scenario: Seen comment
- **WHEN** the student has opened the reviewed answer
- **THEN** the notice no longer appears
