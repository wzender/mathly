## ADDED Requirements

### Requirement: Students never call the AI
A student's request, a photographed problem or an answer to check, SHALL become a request in the AI queue of the class's teacher, and nothing SHALL be sent to the AI until the teacher or a developer sends it. A student SHALL have at most 5 requests waiting and 20 photos a day. A student in several classes SHALL choose which class's teacher gets it, defaulting to the class with the nearest coming test, then the one used last.

#### Scenario: A photo
- **WHEN** a student photographs a problem
- **THEN** a waiting request is made, the AI is not called, and the student's page shows it waiting

#### Scenario: Too many
- **WHEN** a student already has 5 requests waiting and makes another
- **THEN** it is refused with a message saying why

### Requirement: Cancel and decline
A student SHALL be able to cancel a waiting request. The teacher SHALL be able to decline a request with an optional note, which the student then sees. Cancelling or declining a help photo SHALL delete its picture.

#### Scenario: Declined with a note
- **WHEN** a teacher declines a request and writes "צלמו שוב, יותר קרוב"
- **THEN** the student sees the request declined with that note, and the photo is deleted

### Requirement: Who sends straight
A teacher or a developer SHALL send without the queue when the request is their own. Everyone else's requests SHALL wait in the queue; a teacher sees the queue of their own classes' students, a developer sees every queue, and nobody else sees any.

#### Scenario: A teacher's own photo
- **WHEN** a teacher photographs a problem for themselves
- **THEN** it is sent at once and counts against their allowance

#### Scenario: Another teacher's queue
- **WHEN** a teacher asks for the queue of a class they do not teach
- **THEN** it is not shown to them

### Requirement: Photographed-problem help
The AI SHALL read the photographed problem and answer in a fixed shape: the problem as it read it, the solution in steps each with a hint that does not give the step away and the step itself, the final answer, and the path skill the problem practises. The student's page SHALL show the hints one by one and the steps and the answer only when asked. An unreadable photo SHALL say what to photograph again.

#### Scenario: Hints first
- **WHEN** a student opens a finished help request
- **THEN** only the first hint shows, and each next hint, the step and the answer appear only on request

### Requirement: Where the student finds photo help
Photo help SHALL appear only for students of a class with the AI on: on the exercise screen beside the help, telling the teacher which skill the student was on, and on the home screen as a card that also lists the student's open requests with their state. It MUST NOT appear on the path. The sheet SHALL say that the teacher sees the picture first.

#### Scenario: AI off
- **WHEN** a student's class has the AI off
- **THEN** no photo help button or card is shown

### Requirement: AI check of a handwritten answer
A student or a teacher SHALL be able to ask for an AI check of a handed-in answer. The AI SHALL be given the question as it was when answered (a stored copy) and the answer pictures, and SHALL return a score, a comment and what it read. It is a suggestion: the teacher's grade wins, the AI's check is never edited, and an unreadable or unsure answer gets no score.

#### Scenario: A suggestion
- **WHEN** an AI check finishes for a handed-in answer
- **THEN** the teacher opening it in the inbox sees the suggested score and comment, and gives their own grade

#### Scenario: Unsure
- **WHEN** the AI cannot read the answer
- **THEN** no score is stored and the teacher is told to look at it themselves

### Requirement: Asking the teacher to look again
A student who disagrees with a check or a grade SHALL be able to ask the teacher to look again: at most one open request per answer and five per student. The request SHALL appear in the teacher's inbox and SHALL close when the teacher saves a grade or sends the answer back.

#### Scenario: One open
- **WHEN** a student asks again about an answer that already has an open request
- **THEN** it is refused

#### Scenario: Closed by a grade
- **WHEN** the teacher grades an answer with an open request
- **THEN** the request is closed

### Requirement: The teacher's AI queue
The teacher's screen SHALL have an AI tab, with its number of waiting requests, listing each waiting request with the student, the picture, the kind and, for a photo from the exercise screen, the skill. The teacher SHALL send it to the AI or decline it with a note. A request being processed or failed SHALL show its state.

#### Scenario: Send
- **WHEN** the teacher sends a waiting request
- **THEN** it becomes processing at once, and done or failed when the AI finishes, and the student's page follows

### Requirement: Batches
A teacher SHALL be able to send every waiting request of one scope in a single action, oldest first: one assignment's checks, or the single help photos. When the budget is short it SHALL send what is left and keep the rest waiting for the next day.

#### Scenario: Short budget
- **WHEN** a batch of 10 is sent and the class has 4 checks left today
- **THEN** 4 are sent, 6 stay waiting, and the teacher is told

### Requirement: Budgets
Each class SHALL have a daily number of AI checks, counted by the Israel date and taken in one step in the database so two batches at once never pass it. A call that fails, or whose picture the AI could not read, SHALL be given back. A teacher SHALL also have 3 AI requests a day of their own; developers have no limit and students are not counted.

#### Scenario: Two at once
- **WHEN** two batches run at the same time with 1 check left
- **THEN** exactly one request is sent

#### Scenario: A failed call
- **WHEN** an AI call fails
- **THEN** its check is given back to the budget

### Requirement: When the AI fails
The people who can fix it, the teacher who sent it and a developer, SHALL see the cause and what to do: missing key, invalid key, no permission, model not found, no credit, rate limit, overloaded, no connection, refused, cut short or an unusable answer, with the technical detail. The student SHALL see only a short "try again later".

#### Scenario: No credit
- **WHEN** the provider says there is no credit
- **THEN** the teacher sees "no credit" with what to do, and the student sees "נסו שוב מאוחר יותר"

### Requirement: Usage and cost
Every AI call SHALL record its model, tokens and estimated cost, with the feature (photo or check). A failure to record MUST NOT fail the request.

#### Scenario: A call
- **WHEN** an AI call finishes
- **THEN** a usage row with its tokens and cost is saved

### Requirement: AI privacy
The AI SHALL be off for a class until a manager switches it on for that class. A student of a class with the AI off SHALL see no AI buttons, and the server SHALL refuse their requests. Nothing that names a student, a name or an email, MUST be sent to the AI: only the picture and the question. Before a first photo the student SHALL see a reminder not to write their name or personal details in it.

#### Scenario: Off
- **WHEN** a student of a class with the AI off sends a photo request to the server
- **THEN** it is refused

#### Scenario: What is sent
- **WHEN** a request is sent to the AI
- **THEN** the payload holds the picture and the question and no name or email
