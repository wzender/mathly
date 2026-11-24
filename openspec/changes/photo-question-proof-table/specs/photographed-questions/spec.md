## ADDED Requirements

### Requirement: Geometry questions are solved in a claim/reason table
The system SHALL show a claim/reason table (one for each part) for a photographed question the AI marks as solved by claims and reasons, with a symbol bar and suggested reasons, and SHALL require at least one claim to hand it in, the board being optional.

#### Scenario: Handing in a table without a board
- **WHEN** the student fills rows of the table and hands in without writing on the board
- **THEN** the question is checked from the table

#### Scenario: An empty table
- **WHEN** the student hands in with no claim in the table
- **THEN** the hand-in is refused with a message to fill the table

### Requirement: The check reads the table row by row
The system SHALL send the table to the AI as numbered rows with their parts, mark missing reasons, and keep the handed-in rows for the student, the teacher and the tutor.

#### Scenario: A missing reason
- **WHEN** a row has a claim and no reason
- **THEN** the AI receives that row with its reason marked as missing

### Requirement: The next-step hint fills the table
The system SHALL put a revealed step of a claim/reason question into the first empty row of its part, or a new row.

#### Scenario: Asking for the next step
- **WHEN** the student asks for the next step
- **THEN** the step's claim and reason appear in the next empty row
