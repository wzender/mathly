# Spec Delta

## MODIFIED Requirements

### Requirement: Choosing a subject
After sign-in a student SHALL first see the subjects of their classes as cards, each with its name, its icon and a bar "N מתוך M מיומנויות" counting that subject's skills, in a fixed order with math first. Math's card SHALL be named "מתמטיקה כיתה ט - מצוינות". Tapping a card SHALL open that subject's home, reached by the tab bar, and every screen of the subject SHALL have a way back to the subjects.

#### Scenario: After signing in
- **WHEN** a student whose classes study math only signs in
- **THEN** they see a card "מתמטיקה כיתה ט - מצוינות" with "N מתוך M מיומנויות", and no path yet

#### Scenario: Two subjects
- **WHEN** a student whose classes study math and "מדעים" signs in
- **THEN** they see the math card first and a "מדעים" card, each counting only its own skills

#### Scenario: Opening the subject
- **WHEN** the student taps the "מדעים" card
- **THEN** the "מדעים" home opens, with the tab bar and a way back to the subjects

#### Scenario: A link to a skill
- **WHEN** a student opens `#/skill/<id>` directly or reloads the page on it
- **THEN** the path of that skill's subject opens with that skill's exercise screen over it

### Requirement: Trail of lesson hubs
Every lesson of the open subject that the student's classes study SHALL be a hub showing its name and "mastered of total", with its skills in a ring around it, in order, numbered from the top and clockwise. The hubs SHALL be joined by a vertical trail from a start marker with the owl to an end marker. Lessons of other subjects MUST NOT appear on it.

#### Scenario: Opening the path
- **WHEN** a student opens the path
- **THEN** each of their lessons is a hub with its numbered skills around it, on one trail

#### Scenario: Another subject's lessons
- **WHEN** a student who studies math and "מדעים" opens the "מדעים" path
- **THEN** only the "מדעים" lessons are on it, in the subject's order

### Requirement: Next skill
One skill of the open subject SHALL carry the owl as the suggested next: the subject's unmastered skill answered most recently, else its first unmastered skill in the subject's order. When all are mastered none is marked. The marker MUST NOT lock, hide or reorder anything.

#### Scenario: New student
- **WHEN** a student who answered nothing opens the path
- **THEN** the owl is on the first skill of the first lesson and every skill can be opened

#### Scenario: Continuing
- **WHEN** a student's last answer was on an unmastered skill
- **THEN** the owl is on that skill

#### Scenario: Answering in another subject
- **WHEN** a student last answered in "מדעים" and opens the math path
- **THEN** the owl is on math's most recently answered unmastered skill, not on the "מדעים" skill
