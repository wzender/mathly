# Spec Delta

## Purpose

Lets a class teacher hand out a worksheet (a PDF or photos) as part of an assignment, lets students open it and hand in a photographed solution, and lets the teacher check each submission.

## ADDED Requirements

### Requirement: Class teacher attaches a worksheet to an assignment
The class teacher of a class, or a manager, SHALL be able to add a worksheet item to an assignment of that class. The worksheet has a title of up to 80 characters and is one PDF of up to 10 pages and 10 MB, or 1 to 10 photos (JPEG, PNG or WebP, up to 5 MB each). An assignment SHALL have at most 5 worksheet items. Any other account MUST be refused.

#### Scenario: Teacher attaches a PDF
- **WHEN** the teacher of 9א uploads a 3-page PDF titled "דף עבודה – פיתגורס" and saves the assignment with it
- **THEN** the assignment has a worksheet item with that title and 3 pages

#### Scenario: Teacher attaches photos
- **WHEN** the teacher uploads 2 photos as one worksheet
- **THEN** the worksheet has 2 pages, in the order they were chosen

#### Scenario: File refused
- **WHEN** the teacher uploads a PDF of 11 pages, a file over the size limit, or a file that is not a PDF or an image
- **THEN** the server refuses it with an error naming the limit, and nothing is stored

#### Scenario: Not the class teacher
- **WHEN** a student or a teacher of another class tries to upload a worksheet for 9א
- **THEN** the server refuses with a forbidden error

#### Scenario: Worksheet of another class
- **WHEN** an assignment of 9א is saved with a worksheet item uploaded for 9ב
- **THEN** the server rejects the assignment

### Requirement: Worksheet files stay private
Worksheet files and submission photos SHALL be readable only through the server, by the class's students (worksheets), the student who handed in (their own submission), and the class teacher or a manager. Responses to the browser MUST NOT contain storage paths. Uploaded images SHALL be stored without their metadata (such as location).

#### Scenario: Student of another class
- **WHEN** a student who is not in 9א asks for a page of a 9א worksheet
- **THEN** the server answers not found

#### Scenario: Another student's submission
- **WHEN** a student asks for a page of a classmate's submission
- **THEN** the server answers not found

### Requirement: Students open the worksheet
A student SHALL be able to open each worksheet of their classes' assignments from the assignment card, see its pages one under the other, and download the original file (the PDF, or the photos).

#### Scenario: Student opens a PDF worksheet
- **WHEN** a student of 9א opens "דף עבודה – פיתגורס" from "משימות מהמורה"
- **THEN** the 3 pages are shown as images, with a button to download the PDF

### Requirement: Students hand in a solution
A student SHALL be able to hand in a solution to a worksheet as 1 to 10 photos. Until the teacher checks the submission, the student SHALL be able to replace it with a new set of photos; the new set replaces the old one. A submission after the due date SHALL be accepted.

#### Scenario: Hand in
- **WHEN** a student photographs 2 pages of their solution and sends them
- **THEN** the submission is stored with 2 pages and the time it was handed in

#### Scenario: Replace before the check
- **WHEN** a student who handed in sends a new set of photos before the teacher checked
- **THEN** only the new set is kept, with the new time

#### Scenario: Replace after the check
- **WHEN** a student tries to hand in again after the teacher checked the submission
- **THEN** the server refuses, and the checked submission stays as it was

#### Scenario: Not in the class
- **WHEN** a student who is not in 9א tries to hand in a 9א worksheet
- **THEN** the server answers not found

### Requirement: Worksheet item completion
A worksheet item SHALL be done for a student when the student has a submission for it. It SHALL be late when it was handed in after the end of the due date, Jerusalem time. The same rule SHALL be used on the student's card and in the teacher's report.

#### Scenario: Handed in on time
- **WHEN** the due date is 12/11 and the student handed in on 12/11 at 22:00 Jerusalem time
- **THEN** the item is done and not late

#### Scenario: Handed in late
- **WHEN** the student handed in on 13/11
- **THEN** the item is done late

#### Scenario: Not handed in
- **WHEN** the student opened the worksheet but did not hand in
- **THEN** the item is not done

### Requirement: Teacher follows and checks submissions
In the class report's assignments tab, the teacher SHALL see for each worksheet which students handed in (on time or late), which are missing, and how many submissions wait for a check. The teacher SHALL be able to open a submission, see its pages, and mark it checked with an optional score from 0 to 100 and an optional comment of up to 1000 characters. The teacher SHALL be able to change the score and comment later.

#### Scenario: Waiting for a check
- **WHEN** 3 of 20 students handed in and none was checked
- **THEN** the worksheet shows 3 handed in, 17 missing and 3 waiting for a check

#### Scenario: Teacher checks a submission
- **WHEN** the teacher opens Dana's submission, gives 85 and writes "יפה, שימי לב ליחידות"
- **THEN** the submission is checked, with that score and comment, and is no longer counted as waiting

#### Scenario: Score out of range
- **WHEN** the teacher sends a score of 120
- **THEN** the server rejects it

### Requirement: Student sees the check
After the teacher checks a submission, the student SHALL see on the assignment card that it was checked, with the score and the comment when given.

#### Scenario: Checked with a comment
- **WHEN** the teacher checked Dana's submission with 85 and a comment
- **THEN** Dana's card shows "נבדק", 85 and the comment

### Requirement: Removing a worksheet removes its submissions
When an assignment is deleted, or a worksheet item is removed from it, the worksheet, its files, and its submissions SHALL be deleted. The form SHALL ask for confirmation, naming how many students handed in. A worksheet uploaded but never saved into an assignment SHALL be deleted after 24 hours.

#### Scenario: Worksheet removed from an assignment
- **WHEN** the teacher removes a worksheet that 4 students handed in, and confirms
- **THEN** the worksheet and the 4 submissions are gone, and the students no longer see the item

#### Scenario: Upload never saved
- **WHEN** the teacher uploads a worksheet and closes the form without saving
- **THEN** the worksheet is deleted within a day

### Requirement: Works without the migration
When the worksheet storage is not set up, the server SHALL answer worksheet routes with an "unavailable" error, the assignment form SHALL not offer worksheets, and the rest of assignments SHALL keep working.

#### Scenario: Tables missing
- **WHEN** the worksheet migration was not applied and a teacher opens the assignment form
- **THEN** the form has no worksheet option, and assignments without worksheets save as before
