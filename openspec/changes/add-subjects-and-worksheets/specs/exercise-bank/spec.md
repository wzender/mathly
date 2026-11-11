# Spec Delta

## MODIFIED Requirements

### Requirement: Bank is the content source
Lessons, skills, multiple-choice questions and mistakes SHALL come from the exercise bank: the math content file kept from mathly1, and the lessons published in the database (see `subjects` and `worksheet-lessons`). Every question SHALL have exactly one correct choice, and each wrong choice SHALL point to a mistake with a name and a tip. A mistake MAY also name a skill to go back to.

#### Scenario: Wrong choice
- **WHEN** a student picks a wrong choice
- **THEN** the mistake it points to supplies the feedback's name and tip

#### Scenario: Mistake without a skill to go back to
- **WHEN** a mistake names no skill to go back to
- **THEN** the feedback shows its name and tip with no link

#### Scenario: A published lesson
- **WHEN** a student picks a wrong choice in a lesson published from a worksheet
- **THEN** that lesson's mistake supplies the feedback's name and tip, as for a math lesson

### Requirement: Bank checked at start
The server SHALL check the bank when it starts: unique ids, one correct choice per question, and every mistake and skill referred to exists. A broken math content file SHALL stop the server from starting and say what is wrong. A published lesson that fails the check SHALL be left out and logged with what is wrong, and the server SHALL start without it.

#### Scenario: Unknown mistake
- **WHEN** a choice in the math content file points to a mistake id that does not exist
- **THEN** the server does not start and names the question and the id

#### Scenario: A broken published lesson
- **WHEN** a published lesson in the database fails the check at start
- **THEN** the server starts without that lesson, and the log names the lesson and the problem
