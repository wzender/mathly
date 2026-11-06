# Spec Delta

## Purpose

Gives a student one place that lists everything they owe their teacher, with a clear state for each item, and lets them hand in, add a note and fix returned work from there.

## ADDED Requirements

### Requirement: Student sees one list of owed work
A signed-in student SHALL have a "המשימות שלי" list holding: their open assignments (class-wide and those given to them personally), final quizzes open to them, and worksheets returned to them for a fix. Items SHALL be ordered by due date, nearest first; items without a due date come last. The home screen SHALL show the count of open items and the nearest due date, linking to the list.

#### Scenario: Mixed list
- **WHEN** a student has an assignment due 12/11, a final quiz of unit `g` open until 10/11, and a worksheet returned for a fix due 14/11
- **THEN** the list shows the final quiz first, then the assignment, then the returned worksheet

#### Scenario: Nothing owed
- **WHEN** the student has no open items
- **THEN** the list says there is nothing to do now and links to the path and the grades page

#### Scenario: Personal assignment
- **WHEN** the teacher gave a focus-practice assignment to this student only
- **THEN** it appears in this student's list, marked as personal, and not in a classmate's list

### Requirement: Each item shows one state
Each item in the list SHALL show exactly one state, chosen in this order: returned for a fix, late, waiting for a check, checked, handed in, in progress, not started. The state SHALL be given as text as well as by colour. The same state SHALL be used in the teacher's views of that item.

#### Scenario: Handed in and waiting for the teacher
- **WHEN** a student handed in a worksheet that the teacher has not checked
- **THEN** the item shows "ממתין לבדיקה"

#### Scenario: Late and not handed in
- **WHEN** the due date has passed (Jerusalem time) and the item is not done
- **THEN** the item shows "באיחור"

#### Scenario: Returned work
- **WHEN** the teacher returned a submission for a fix
- **THEN** the item shows "הוחזר לתיקון" with the teacher's comment, even if it is past its due date

### Requirement: Student adds a note when handing in
When handing in a worksheet, the student SHALL be able to add a note to the teacher of up to 300 characters. The teacher SHALL see the note with the submission.

#### Scenario: Note sent with the photos
- **WHEN** a student hands in 2 photos with the note "לא הבנתי את שאלה 3"
- **THEN** the teacher sees the note above the pages of the submission

#### Scenario: Note too long
- **WHEN** the note is longer than 300 characters
- **THEN** the server rejects the hand-in and nothing is stored

### Requirement: Student gets a hand-in receipt
After a hand-in is stored, the student SHALL see a receipt naming the item, the number of pages, the time of hand-in and whether it was on time. The receipt SHALL stay visible on the item until the work is checked.

#### Scenario: Receipt on time
- **WHEN** a student hands in 3 pages before the due date
- **THEN** the item shows "הוגש · 3 עמודים" with the time and no late mark

#### Scenario: Failed hand-in has no receipt
- **WHEN** the upload of a page fails
- **THEN** no receipt is shown, the item keeps its earlier state, and the student can try again

### Requirement: Student hands in a worksheet from the phone
A student SHALL be able to start a worksheet hand-in on the computer and take the photos on a phone signed in to the same account, using the same request, confirm and review steps as answer scans. Pages taken on the phone SHALL be attached only to the worksheet the request was made for.

#### Scenario: Photos from the phone
- **WHEN** a student presses "צילום מהטלפון" on a worksheet and takes 2 photos on the phone
- **THEN** the computer shows the 2 pages under that worksheet, ready to send with an optional note

#### Scenario: Another account
- **WHEN** a phone signed in to another account looks for pending requests
- **THEN** it sees no request of this student

### Requirement: Student fixes returned work
When the teacher returns a worksheet submission for a fix, the student SHALL be able to hand in a new set of photos for it, with a note. The new set SHALL become the submission waiting for a check. The earlier set, its score and the teacher's return comment SHALL stay visible to the student and the teacher as an earlier version.

#### Scenario: Resubmit after a return
- **WHEN** the teacher returned Dana's submission with "חסרה דרך פתרון בשאלה 2" and Dana hands in 2 new photos
- **THEN** the item shows "ממתין לבדיקה", and Dana's earlier version is listed with the return comment

#### Scenario: Not returned
- **WHEN** a student tries to hand in again after the teacher checked the submission without returning it
- **THEN** the server refuses, as before
