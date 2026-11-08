# Spec Delta

## Purpose

Gives students AI help with photographed problems and AI-suggested checks of their written answers, always through their teacher, within a budget, and only where the school has switched it on.

## ADDED Requirements

### Requirement: Students never call the AI
A student's request (a photographed problem or an answer to check) SHALL become a request in the AI queue of their teacher, who sends it to the AI or declines it with an optional note. The student's screen SHALL show the request waiting, then its result or the note, and SHALL let them cancel it.

#### Scenario: Declined
- **WHEN** a teacher declines a photo with the note "זה לא תרגיל במתמטיקה"
- **THEN** the student sees that it was declined, with the note

### Requirement: Request limits
A student SHALL have at most 5 requests waiting at once and at most 20 photos a day.

#### Scenario: Sixth request
- **WHEN** a student with 5 waiting requests sends another
- **THEN** it is refused with a message to wait for the teacher

### Requirement: Which teacher
A student in more than one class SHALL choose which teacher a request goes to, defaulting to the teacher of the class with the nearest upcoming test and then to the one used last. The request SHALL count against that class's budget.

#### Scenario: Two classes
- **WHEN** a student in two classes sends a photo
- **THEN** they are asked which teacher it goes to, with the default already chosen

### Requirement: Who sends straight
A teacher or developer SHALL send their own requests without the queue. A teacher SHALL see the queue of their classes' students; a developer SHALL see every queue.

#### Scenario: Teacher's own photo
- **WHEN** a teacher photographs a problem
- **THEN** it goes straight to the AI, within the teacher's daily allowance

### Requirement: Photo help
The AI SHALL answer a photographed problem with: the problem as it read it, the solution as steps each with a hint and the step itself, the final answer, and the skill it practises. The student SHALL see one hint at a time, and each step and the answer only when asking. The photo MUST NOT be kept.

#### Scenario: Hints first
- **WHEN** a student opens the result of photo help
- **THEN** they see the problem as read and the first hint, and the steps stay hidden until asked

### Requirement: Photo help entries
The photo help button SHALL appear on the exercise screen beside "?" (telling the teacher the current skill) and on home as a card that also lists the student's requests. The "?" help SHALL end with "עדיין תקועים? צלמו", opening photo help.

#### Scenario: From a skill
- **WHEN** a student sends a photo from the exercise screen of "פירוק טרינום"
- **THEN** the teacher's queue shows the request with that skill

### Requirement: AI checks of written answers
The AI SHALL check a handed-in written answer against a stored copy of the question as answered, and return a score and comment as a suggestion. Where a score is used the teacher's SHALL win. The AI's check MUST NOT be edited; the teacher's review is kept beside it and older reviews stay as history.

#### Scenario: Teacher changes the score
- **WHEN** the AI suggests 70 and the teacher gives 85
- **THEN** the grade is 85 and the AI's 70 is still shown as its suggestion

### Requirement: Asking to look again
A student who disagrees with a check SHALL be able to ask the teacher to look again, with at most one open request per answer and five per student. Saving a review SHALL close the request.

#### Scenario: Look again
- **WHEN** a student asks to look again at a checked answer
- **THEN** the request appears in the teacher's inbox

### Requirement: Budgets
Each class SHALL have a daily number of AI checks (default 150) counted by the Israel date and taken in one step, so two batches cannot pass it. A teacher SHALL have 3 personal requests a day; developers have no limit. A failed or unreadable check SHALL be given back.

#### Scenario: Budget reached
- **WHEN** a class has used its 150 checks today
- **THEN** further checks wait until tomorrow

### Requirement: Batches
A teacher SHALL be able to send every pending check of one assignment, or the single answers waiting, in one action, oldest first. When the budget is short the rest SHALL stay pending for the next day.

#### Scenario: Short budget
- **WHEN** a teacher sends a batch of 30 with 10 checks left today
- **THEN** 10 are sent and 20 stay pending

### Requirement: When the AI fails
The teacher who sent a request and developers SHALL see what went wrong and what to do (missing or invalid key, no permission, model not found, no credit, rate limit, overloaded, no connection, refused, cut short, unusable answer). The student SHALL see a short "try again later".

#### Scenario: No credit
- **WHEN** the AI account has no credit left
- **THEN** the teacher sees "no credit" with what to do, and the student sees "try again later"

### Requirement: Cost records
Every AI call SHALL record its tokens and estimated cost, with the class and the kind of call.

#### Scenario: Photo help call
- **WHEN** a teacher sends a photo to the AI
- **THEN** a record with its tokens, cost, class and kind "photo" is kept

### Requirement: AI off until switched on
The AI SHALL be off for a class until a manager switches it on, which the school does after confirming families agree. Students of a class with the AI off SHALL see no AI buttons.

#### Scenario: New class
- **WHEN** a student of a newly created class opens the exercise screen
- **THEN** there is no photo help button

### Requirement: Nothing identifying goes to the AI
Only the picture and the question SHALL be sent to the AI, never a student's name or email. Before a first photo the student SHALL be reminded not to write personal details in it.

#### Scenario: First photo
- **WHEN** a student photographs for the first time
- **THEN** they see a reminder not to write their name in the picture
