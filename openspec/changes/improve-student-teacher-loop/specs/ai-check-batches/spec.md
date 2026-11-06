# Spec Delta

## Purpose

Makes AI checking of student work practical for a whole class: the teacher approves a batch in one action, checks draw from a per-class daily budget instead of the teacher's personal allowance, and the teacher stays the one who confirms what counts.

## ADDED Requirements

### Requirement: Teacher approves a batch of checks
The class teacher SHALL be able to send to the AI, in one action, all pending check requests of one final-quiz window, of one unit's practice sittings, or of one worksheet's submissions. The teacher SHALL see how many checks the batch holds and how many the class budget has left before confirming. Requests outside the teacher's classes MUST NOT be included.

#### Scenario: Final quiz batch
- **WHEN** 27 students handed in a 4-question final quiz and the teacher presses "שליחת כל הבוחן לבדיקה"
- **THEN** the app shows "108 בדיקות · נשארו 150 היום", and on confirmation the 108 requests are sent

#### Scenario: Worksheet batch
- **WHEN** a worksheet has 12 submissions without an AI suggestion and the teacher sends them as a batch
- **THEN** each submission gets an AI suggestion, shown in its review form

### Requirement: Checks of student work use a class budget
Checks of student work SHALL count against a daily budget of the student's class (Jerusalem date), not against the teacher's personal daily AI allowance. A manager SHALL set each class's budget; a class without a setting SHALL use a default of 150 checks a day. A check that fails or could not read the photo SHALL be given back.

#### Scenario: Teacher's own allowance untouched
- **WHEN** the teacher sends a batch of 108 checks
- **THEN** the teacher can still make their own 3 AI requests that day

#### Scenario: Unreadable photo given back
- **WHEN** the AI marks one answer unreadable
- **THEN** the class budget used goes down by one for that answer

### Requirement: Budget running out
When a batch needs more checks than the budget has left, the teacher SHALL be able to send as many as are left, oldest first. The rest SHALL stay pending and SHALL be offered again the next day. The student SHALL see their request as waiting, not failed.

#### Scenario: Partial batch
- **WHEN** a batch holds 108 checks and 40 are left today
- **THEN** 40 are sent now, 68 stay pending, and the teacher sees "68 יישלחו מחר"

### Requirement: Teacher may auto-send practice checks
The class teacher SHALL be able to turn on, per class, automatic sending of practice-quiz checks. When on, a handed-in practice sitting's answers SHALL be sent to the AI without waiting for the teacher, within the class budget. Final-quiz and worksheet checks SHALL always wait for the teacher's approval. The setting SHALL be off by default.

#### Scenario: Auto-send on
- **WHEN** auto-send is on for 9א and a student hands in a practice sitting
- **THEN** its answers are checked without the teacher's action, and the student sees the result when it completes

#### Scenario: Final quiz with auto-send on
- **WHEN** auto-send is on and a student hands in a final sitting
- **THEN** its answers wait in the teacher's queue

### Requirement: AI results are the teacher's to confirm
A worksheet's AI check SHALL only fill the review form; nothing SHALL reach the student until the teacher saves the check. A quiz answer's AI score SHALL count unless the teacher saves a review, and final results SHALL reach students only on release. Answers the AI could not score SHALL go to the teacher's inbox.

#### Scenario: Worksheet suggestion not saved
- **WHEN** the AI suggests 70 for a worksheet submission and the teacher has not saved it
- **THEN** the student sees "ממתין לבדיקה" and no score

#### Scenario: Needs review
- **WHEN** the AI ends a quiz answer's check with "needs review"
- **THEN** the answer appears in the teacher's inbox

### Requirement: Student sees where their check is
For each answer or submission sent for checking, the student SHALL see one of: waiting for the teacher to send, checking, checked, waiting for the teacher's review, or declined (with the teacher's note).

#### Scenario: Waiting for the teacher
- **WHEN** a student's final-quiz answers are pending in the queue
- **THEN** the result screen shows "ממתין לאישור המורה לבדיקה" for each answer

### Requirement: Teacher sees AI use per class
The teacher SHALL see, per class, the checks used and left today, and the checks used in the last 7 days.

#### Scenario: Budget view
- **WHEN** the teacher opens the AI queue
- **THEN** each class shows "נוצלו 108 מתוך 150 היום" and the last 7 days' total
