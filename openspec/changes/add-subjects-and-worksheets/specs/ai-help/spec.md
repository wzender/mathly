# Spec Delta

## MODIFIED Requirements

### Requirement: Photographed-problem help
The AI SHALL be told the subject of the skill the student was on, and its skills. It SHALL read the photographed problem and answer in a fixed shape: the problem as it read it, the solution in steps each with a hint that does not give the step away and the step itself, the final answer, and the skill of that subject the problem practises. The student's page SHALL show the hints one by one and the steps and the answer only when asked. An unreadable photo SHALL say what to photograph again.

#### Scenario: Hints first
- **WHEN** a student opens a finished help request
- **THEN** only the first hint shows, and each next hint, the step and the answer appear only on request

#### Scenario: Help in another subject
- **WHEN** a student sends a photo from a "מדעים" skill's exercise screen
- **THEN** the AI is told the subject "מדעים" and its skills, and the answer names a "מדעים" skill, not a math one
