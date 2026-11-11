## ADDED Requirements

### Requirement: System status card
The developer's home SHALL start with a status card that only a developer can read. It SHALL show one overall state (ok, warning or error), the running version, the date of the last update, when the server started, and one row per part of the system: the database, sign-in, the question bank, AI help, phone notifications, answer pictures and the hourly cleanup. The database row SHALL ask the database itself, not a cache. A secret or key MUST NOT be shown, only whether it is set. Any part in error SHALL make the overall state an error; otherwise any warning SHALL make it a warning.

#### Scenario: A developer opens their home
- **WHEN** a developer opens the developer screen
- **THEN** the card shows the version, the last update date in Israel's time, and a row for each part with its state

#### Scenario: The database does not answer
- **WHEN** the database refuses or times out during the check
- **THEN** its row is an error and the overall state is an error

#### Scenario: Not a developer
- **WHEN** a teacher asks for the status
- **THEN** the server refuses with 403

#### Scenario: A key is set
- **WHEN** the AI key is set
- **THEN** the AI row is ok and the key's value appears nowhere in the response
