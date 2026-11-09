## MODIFIED Requirements

### Requirement: Choosing a subject
After sign-in a student SHALL first see the subjects of their classes as cards, each with its name and a bar "N מתוך M מיומנויות". Math is the only subject, and its card is named "מתמטיקה כיתה ט - מצוינות". Tapping a card SHALL open the subject's home, reached by the tab bar, and every screen of the subject SHALL have a way back to the subjects.

#### Scenario: After signing in
- **WHEN** a student signs in
- **THEN** they see a card "מתמטיקה כיתה ט - מצוינות" with "N מתוך M מיומנויות", and no path yet

#### Scenario: Opening the subject
- **WHEN** the student taps the math card
- **THEN** the math home opens, with the tab bar and a way back to the subjects

#### Scenario: A link to a skill
- **WHEN** a student opens `#/skill/<id>` directly or reloads the page on it
- **THEN** the math path opens with that skill's exercise screen over it
