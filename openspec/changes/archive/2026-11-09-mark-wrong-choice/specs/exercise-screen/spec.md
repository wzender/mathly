## MODIFIED Requirements

### Requirement: A wrong answer
A wrong answer SHALL be quiet and SHALL show the name and tip of the mistake attached to the chosen choice, about the mistake and not the student. The chosen choice SHALL be marked as wrong with a symbol and a word on the choice itself ("✗ לא נכון"), not by colour alone, and no other choice SHALL be marked. It MUST NOT reveal the correct answer. When the mistake names a skill to go back to, the feedback SHALL link to it.

#### Scenario: Sign mistake
- **WHEN** a student picks a choice tagged with "טעות סימן באיבר האמצעי"
- **THEN** the mistake's name and tip are shown and no choice is marked as correct

#### Scenario: The chosen choice is marked
- **WHEN** a student picks a wrong choice
- **THEN** that choice shows "✗ לא נכון" and a stronger border, and every other choice looks as it did
