## ADDED Requirements

### Requirement: One primary action on home
The system SHALL show the current lesson as the only gold, raised button on home, and closing the gaps, quick practice and the photographed question as visibly secondary buttons.

#### Scenario: Lessons behind
- **WHEN** lessons are behind and home shows the gaps button
- **THEN** it is a flat card with a warm edge, not a second gold button

### Requirement: An open app takes an update
The system SHALL send this build's version with every answer and SHALL reload an app that is open on an older build at its next change of screen, not in the middle of a question.

#### Scenario: Left open during an update
- **WHEN** an app opened before an update gets an answer from the new build
- **THEN** it reloads when the student moves to another screen, with the new styles
