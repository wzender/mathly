## ADDED Requirements

### Requirement: Thinking indicator
As soon as a choice is tapped, the sheet SHALL show that the answer is being checked: the tapped choice shows a spinner, a status line says "בודקים…", and the other choices are dimmed and cannot be tapped. The indicator SHALL go away when the answer arrives or fails, and it MUST NOT depend on motion: with reduced motion the words are shown and the spinner is still.

#### Scenario: A slow answer
- **WHEN** a student taps a choice and the server takes two seconds
- **THEN** during those two seconds the tapped choice shows a spinner, "בודקים…" is shown and the other choices cannot be tapped, and the result replaces them when it arrives

#### Scenario: An error
- **WHEN** the answer cannot be sent
- **THEN** the indicator goes away, the choices can be tapped again and the error is shown
