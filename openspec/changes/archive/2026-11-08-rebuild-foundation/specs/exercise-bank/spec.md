# Spec Delta

## MODIFIED Requirements

### Requirement: Bank is the content source
Lessons, skills, multiple-choice questions and mistakes SHALL come from the exercise bank kept from mathly1. Every question SHALL have exactly one correct choice, and each wrong choice SHALL point to a mistake with a name and a tip. A mistake MAY also name a skill to go back to.

#### Scenario: Wrong choice
- **WHEN** a student picks a wrong choice
- **THEN** the mistake it points to supplies the feedback's name and tip

#### Scenario: Mistake without a skill to go back to
- **WHEN** a mistake names no skill to go back to
- **THEN** the feedback shows its name and tip with no link

### Requirement: Math is rendered
Math written inside `$…$` in the bank SHALL be shown as formulas. A question with a geometry figure or a graph SHALL show it.

#### Scenario: Question with math
- **WHEN** a question's text contains `$x^2+5x+6$`
- **THEN** the student sees it as a formatted formula

#### Scenario: Question with a figure
- **WHEN** a question has a geometry figure
- **THEN** the figure is drawn under the question's text

## REMOVED Requirements

### Requirement: Content gaps are filled before use
**Reason**: The worked-example and faded-example stages are not part of the app, lesson quizzes are drawn from existing questions, and every skill works without extra content.
**Migration**: Use Requirement: Content gaps are listed.

## ADDED Requirements

### Requirement: Bank checked at start
The server SHALL check the bank when it starts: unique ids, one correct choice per question, and every mistake and skill referred to exists. A broken bank SHALL stop the server from starting and say what is wrong.

#### Scenario: Unknown mistake
- **WHEN** a choice points to a mistake id that does not exist
- **THEN** the server does not start and names the question and the id

### Requirement: No answers on the device
A practice, quiz or test question sent to the device MUST NOT carry any sign of which choice is correct. The server SHALL grade.

#### Scenario: Reading the network
- **WHEN** a student looks at the question the device received
- **THEN** nothing in it marks the correct choice

### Requirement: Content gaps are listed
A tool SHALL list what the bank still lacks: skills without a solved example, skills without questions or with few, and mistakes without a skill to go back to.

#### Scenario: Skill without questions
- **WHEN** the tool runs on the current bank
- **THEN** it lists the skill that has no multiple-choice question
