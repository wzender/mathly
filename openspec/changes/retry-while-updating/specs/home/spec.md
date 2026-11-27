## ADDED Requirements

### Requirement: Requests wait out an update
The system SHALL send again, over about half a minute and with a visible "the site is updating" note, a request answered by the host with 502, 503 or 504 without the server's JSON or that failed to connect, and SHALL then say that the site is updating; it SHALL NOT send again a request the server itself refused.

#### Scenario: A short restart
- **WHEN** the host answers 503 twice and then the server answers
- **THEN** the student sees the note while waiting and then the screen, with no error

#### Scenario: The server's own 503
- **WHEN** the server answers 503 with its reason
- **THEN** the request is not sent again and the reason is shown
