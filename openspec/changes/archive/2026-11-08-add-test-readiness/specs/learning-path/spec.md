## MODIFIED Requirements

### Requirement: Choosing a subject
After sign-in a student SHALL first see the subjects of their classes as cards, each with an icon, the subject's name and a bar "N מתוך M מיומנויות" (skills mastered of all skills in their lessons). Math (מתמטיקה) is the only subject; other subjects are not built. Tapping a card SHALL open that subject's home (as in mathly1), from where the tab bar leads to the path, the grades and the collection; the subject's screens SHALL have a way back to the subjects. A reload or a link to a skill SHALL open its path directly.

#### Scenario: After signing in
- **WHEN** a student signs in
- **THEN** they see a card "מתמטיקה" with "N מתוך M מיומנויות", and no path yet

#### Scenario: Opening the subject
- **WHEN** the student taps the math card
- **THEN** the math home opens, with the tab bar and a way back to the subjects

#### Scenario: A link to a skill
- **WHEN** a student opens `#/skill/<id>` directly
- **THEN** the math path opens with that skill's exercise screen over it
