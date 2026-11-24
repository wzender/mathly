## ADDED Requirements

### Requirement: A photographed question is read with all its sub-parts
The system SHALL read a photographed question with its givens and every sub-part, each part on its own line, and keep its answer as a line a part.

#### Scenario: A question with three parts
- **WHEN** the photo shows a question with parts א, ב and ג
- **THEN** the student sees the givens and all three parts, each on its own line

### Requirement: A final-answer box for each numeric sub-part
The system SHALL show a final-answer box, labelled with the part's letter, for each sub-part whose answer is a plain number, and none for a proof.

#### Scenario: Two numeric parts and a proof
- **WHEN** the answers are "א. ∠B = 30°", "ב. BP = 12 ס\"מ" and "ג. הוכחה"
- **THEN** there are two boxes, "∠B = __ °" for א and "BP = __ ס\"מ" for ב

### Requirement: One grade with feedback for each sub-part
The system SHALL grade a question with sub-parts as a whole (equal weight a part) and show a verdict and one sentence of feedback for each part.

#### Scenario: One part wrong
- **WHEN** part א is right and part ב is wrong
- **THEN** the student sees one grade, and part ב marked wrong with its feedback
