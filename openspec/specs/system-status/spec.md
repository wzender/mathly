# system-status Specification

## Purpose
A developer sees at a glance whether each part of the running system works, which version runs and when it was last updated (PRD DEV-5).

## Requirements

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

### Requirement: Activity chart
The developer's home SHALL show, below the status card, how many different people were active on each Israel calendar day of the last 7 days, or of the last 30 days when chosen, with days without activity shown as zero. A person is active on a day when they answered a practice question or started a quiz or a test that day, and SHALL be counted once that day however much they did. The card SHALL also show today's count and the number of different people over the whole range. Only counts SHALL be returned, never who was active, and only a developer can read them.

#### Scenario: A week of activity
- **WHEN** one student answered two questions today and another answered one two days ago
- **THEN** today's column shows 1, the column two days ago shows 1, and the week shows 2 different people

#### Scenario: Late at night
- **WHEN** a student starts a quiz at 00:30 Israel time
- **THEN** it counts on that Israel day, not on the day before in UTC

#### Scenario: A month
- **WHEN** the developer chooses 30 days
- **THEN** the chart has 30 columns and the total counts different people over the 30 days
