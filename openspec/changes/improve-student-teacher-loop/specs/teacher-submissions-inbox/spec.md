# Spec Delta

## Purpose

Gives the class teacher one queue of everything students handed in that waits for them — worksheet submissions, quiz answers, requests to look again — and lets them check, return for a fix or release results from there.

## ADDED Requirements

### Requirement: Teacher sees one inbox of waiting work
The class teacher SHALL have an inbox listing, for their classes: worksheet submissions not checked, final and practice quiz answers whose check needs the teacher (no score, unreadable, needs review, or AI result not yet confirmed), and open requests to look again. Each entry SHALL show the student, the item, the hand-in time, whether it was late, and its state. A manager SHALL see the inbox of every class.

#### Scenario: Mixed inbox
- **WHEN** a class has 3 unchecked worksheet submissions, 2 unreadable quiz answers and 1 request to look again
- **THEN** the inbox lists 6 entries, oldest first

#### Scenario: Teacher of another class
- **WHEN** a teacher asks for the inbox of a class they do not teach
- **THEN** the server refuses with a forbidden error

### Requirement: Inbox can be filtered
The teacher SHALL be able to filter the inbox by class, by assignment or final quiz, by kind (worksheet, quiz answer, request) and by state, and the home of the teacher's page SHALL show the number of open entries.

#### Scenario: Filter by assignment
- **WHEN** the teacher filters by "חזרה לפני המבחן"
- **THEN** only entries of that assignment are listed

### Requirement: Teacher checks in sequence
Opening an entry SHALL show the student's pages, the student's note, the AI suggestion when there is one, and the review form. Saving SHALL move to the next entry of the same filter.

#### Scenario: Next entry
- **WHEN** the teacher saves a check on the first of 3 submissions of a worksheet
- **THEN** the second submission opens

### Requirement: Teacher returns a worksheet for a fix
The teacher SHALL be able to return a worksheet submission for a fix with a comment of 1 to 1000 characters and an optional new due date. A returned submission SHALL not count as waiting for a check and SHALL let the student hand in again. The item SHALL count as done only when a later version is handed in.

#### Scenario: Return with a comment
- **WHEN** the teacher returns Dana's submission with "חסרה דרך פתרון בשאלה 2" and a new due date of 16/11
- **THEN** Dana's item shows "הוחזר לתיקון" with the comment and the new date, and the inbox no longer lists it

#### Scenario: Return without a comment
- **WHEN** the teacher returns a submission with an empty comment
- **THEN** the server rejects it

#### Scenario: Resubmitted version comes back
- **WHEN** Dana hands in a new version
- **THEN** it appears in the inbox as a new entry marked as a second version, with the earlier version reachable

### Requirement: Teacher releases final quiz results
For each final-quiz window, the teacher SHALL see how many sittings are fully checked and SHALL be able to release the results. Releasing with sittings not fully checked SHALL ask for confirmation, and those sittings' results SHALL be shown to their students when their checks complete.

#### Scenario: All checked
- **WHEN** 27 of 27 sittings are checked and the teacher presses "פרסום תוצאות"
- **THEN** all 27 students see their grades

#### Scenario: Some still open
- **WHEN** 25 of 27 are checked and the teacher confirms the release
- **THEN** 25 students see their grades now, and the other 2 when their checks complete
