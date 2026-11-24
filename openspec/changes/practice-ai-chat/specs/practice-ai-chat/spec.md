## ADDED Requirements

### Requirement: An AI chat on practice questions
The system SHALL offer, when the AI is configured, a chat with the AI tutor on the practice exercise screen about the question on screen, and SHALL NOT offer it in quizzes, the written simulation or test rounds.

#### Scenario: Asking about a practice question
- **WHEN** a student opens 💬 on a practice question and asks "איך מתחילים?"
- **THEN** the AI's reply appears under the question

### Requirement: The tutor does not reveal the answer before the student answers
The system SHALL tell the tutor not to reveal the right choice while the question is unanswered, and SHALL not count for mastery an answer given after asking; after the answer, the tutor may explain the right answer and the student's mistake.

#### Scenario: Asking before answering
- **WHEN** the student asks before answering and then answers right
- **THEN** the answer does not count toward the correct-in-a-row run

#### Scenario: Asking after a wrong answer
- **WHEN** the student asks "למה טעיתי?" after a wrong answer
- **THEN** the tutor receives the mistake and may explain the right answer

### Requirement: Limits on the practice chat
The system SHALL allow at most 30 tutor messages a student a day and SHALL say when the AI is not available.

#### Scenario: Over the daily limit
- **WHEN** a student sends a 31st message in a day
- **THEN** the message is refused with a message to come back tomorrow
