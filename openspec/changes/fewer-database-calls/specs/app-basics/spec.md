## ADDED Requirements

### Requirement: Few database round trips
The server SHALL read the same fact once per request, make reads that do not depend on each other at the same time, and keep its connections to the database open for reuse. Opening a student's screen (home, path, skill, grades, collection) SHALL wait for the database at most 3 times in a row, and grading one practice answer at most 4 times in a row.

#### Scenario: Opening a screen
- **WHEN** a student opens the path, home, a skill, the grades or the collection and every database call takes 0.1 seconds
- **THEN** the screen's data arrives in under 0.55 seconds

#### Scenario: Answering
- **WHEN** a student answers a practice question and every database call takes 0.1 seconds
- **THEN** the answer is graded in under 0.75 seconds

#### Scenario: Connections
- **WHEN** the server makes several calls to the database in a row
- **THEN** they reuse an open connection instead of opening a new one each time
