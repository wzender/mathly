# Spec Delta

## Purpose

Lets a manager or a developer turn a worksheet into a lesson: upload it, get an AI draft of skills, multiple-choice questions and mistakes, review and edit everything, then publish it into a subject.

## ADDED Requirements

### Requirement: Uploading a worksheet
A manager or a developer SHALL be able to upload a worksheet as one PDF (up to 20 pages), 1 to 10 photos, or one Word document (.docx), up to 15 MB, and choose an existing subject or name a new one. Any other file SHALL be refused with what is allowed. Nobody else SHALL be able to upload.

#### Scenario: A PDF for a new subject
- **WHEN** a manager uploads a 3-page PDF and names a new subject "מדעים"
- **THEN** the subject "מדעים" is created and a draft lesson is being prepared from the worksheet

#### Scenario: A file that is not allowed
- **WHEN** a manager uploads a spreadsheet
- **THEN** it is refused with the message that a PDF, photos or a Word document are allowed

#### Scenario: A teacher cannot upload
- **WHEN** a teacher asks the server to upload a worksheet
- **THEN** the server refuses with 403

### Requirement: The AI drafts one lesson
The AI SHALL read the worksheet and draft one lesson: a name, its skills each with a name, a short name and a one-line description, and multiple-choice questions for each skill. Each question SHALL have one right choice and two to four wrong ones, and each wrong choice SHALL name a mistake with a name and a tip.

#### Scenario: A worksheet with eight exercises
- **WHEN** the AI drafts a lesson from a worksheet with eight exercises on two topics
- **THEN** the draft has a lesson name, two skills, and questions in which every wrong choice names a mistake with a tip

### Requirement: About ten questions per skill
The draft SHALL hold the worksheet's own exercises, turned into multiple choice, and add similar new questions so each skill has 8 to 12 questions. Each question SHALL say whether it came from the worksheet or was written by the AI, so the reviewer can tell them apart.

#### Scenario: A skill with three exercises on the sheet
- **WHEN** a skill has three exercises on the worksheet
- **THEN** the draft holds those three, marked "מהדף", and 5 to 9 new ones, marked "נכתב על ידי AI"

### Requirement: Drafting status and failure
The uploader SHALL see that the draft is being prepared, then the draft. If the AI cannot read the worksheet, or the call fails, the uploader SHALL see why in words (unreadable file, missing key, no credit, overloaded and the like) and be able to try again without uploading again.

#### Scenario: An unreadable photo
- **WHEN** the AI cannot read a blurry photo
- **THEN** the uploader sees that the worksheet could not be read and is offered to upload a clearer one

#### Scenario: Trying again
- **WHEN** the AI call failed because the service was overloaded and the uploader presses "נסו שוב"
- **THEN** the same worksheet is sent again without a new upload

### Requirement: Editing the draft
The uploader SHALL be able to change, add, delete and reorder everything in the draft: the lesson's name, its skills, the questions and their choices, which choice is right, and the mistakes with their names and tips. Every change SHALL be saved, so leaving and coming back finds the draft as it was.

#### Scenario: Fixing a right answer
- **WHEN** the uploader marks a different choice as the right one and leaves the screen
- **THEN** coming back shows that choice as the right one, and the earlier one as wrong with a mistake to fill in

#### Scenario: Adding a question
- **WHEN** the uploader adds a question to a skill
- **THEN** it is marked as written by a person and saved with the draft

### Requirement: The worksheet beside the draft
While editing, the uploader SHALL see the uploaded worksheet beside the draft, page by page, so each question can be checked against the sheet.

#### Scenario: Checking a question against the sheet
- **WHEN** the uploader opens a draft made from a 2-page PDF
- **THEN** both pages are shown beside the questions

### Requirement: Checks before publishing
Publishing SHALL be refused until the lesson has a name, at least one skill, at least 5 questions per skill, exactly one right choice per question, and a mistake with a name and a tip for every wrong choice. The refusal SHALL list every problem and where it is.

#### Scenario: A wrong choice without a mistake
- **WHEN** the uploader publishes a draft in which one wrong choice of question 4 of skill 2 has no mistake
- **THEN** publishing is refused, and the message points to that choice

### Requirement: Publishing
Publishing SHALL add the lesson to its subject, last in the subject's order. It SHALL reach every student of every class studying that subject at once, without restarting the server, with practice, mastery, the lesson quiz, the review list and grades working as for a math lesson.

#### Scenario: Published into a studied subject
- **WHEN** a manager publishes a lesson in "מדעים" and class ט'3 studies "מדעים"
- **THEN** a student of ט'3 sees the lesson on the "מדעים" path, can practise its skills and can take its quiz

### Requirement: Editing a published lesson
A manager or a developer SHALL be able to edit a published lesson with the same editor and checks. An edited question SHALL count as a new question from then on; answers given to the earlier version SHALL stay in the students' history and mastery.

#### Scenario: Correcting a published question
- **WHEN** a manager corrects the right answer of a published question
- **THEN** students get the corrected question from then on, and their earlier answers to it are kept

### Requirement: Unpublishing
A manager or a developer SHALL be able to unpublish a lesson; it SHALL leave every path, quiz and test choice and become a draft again. A lesson that is in a real test whose date has not passed MUST NOT be unpublished.

#### Scenario: A lesson in a coming test
- **WHEN** a manager unpublishes a lesson that a coming test covers
- **THEN** it is refused, and the message names the test

### Requirement: What the AI is given
The AI SHALL be given only the worksheet's pages and the subject's name. Nothing that names a student, a teacher or a class SHALL be sent to it.

#### Scenario: A worksheet upload
- **WHEN** a manager uploads a worksheet
- **THEN** the AI receives the pages and the subject's name, and no email, class name or person's name

### Requirement: Recording the cost
Every drafting call SHALL be recorded with the AI's usage records (model, tokens and estimated cost) under the feature "worksheet". A failure to record MUST NOT fail the draft.

#### Scenario: A successful draft
- **WHEN** the AI drafts a lesson
- **THEN** a usage record with the feature "worksheet" is stored
