## ADDED Requirements

### Requirement: The teacher reads the practice chats
The system SHALL keep each student's conversation with the AI tutor on a practice question and SHALL show the teacher of the student's class, in the AI tab, the conversations of the last day, week or month, by student, with the skill, the question and whether it was asked before answering.

#### Scenario: A student asked twice about one question
- **WHEN** a student sends two messages about the same practice question on one day
- **THEN** the teacher sees one conversation with the four messages, marked as asked before answering

#### Scenario: Another class
- **WHEN** a teacher of another class opens the AI tab
- **THEN** the conversation is not listed

### Requirement: The chat works before the table exists
The system SHALL answer the student's messages when the conversations table is missing, keeping nothing, and SHALL tell the teacher which migration to run.

#### Scenario: The migration was not run
- **WHEN** the table is missing and a student asks the tutor
- **THEN** the student gets the reply, and the teacher's list says to run the migration
