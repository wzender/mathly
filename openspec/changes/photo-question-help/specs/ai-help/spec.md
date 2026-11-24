## ADDED Requirements

### Requirement: A ladder of hints
A photographed question SHALL offer, before its check, a direction (the grade it can reach becomes 90), the next step (75 for the first, 10 less for each further one) and the full solution (40), and SHALL show the grade it can still reach. The check's grade SHALL be at most that grade.

#### Scenario: A direction and a step
- **WHEN** a student asks how to start and then for the first step, and the check gives 95
- **THEN** the grade is 75

### Requirement: The tutor's conversation
The student SHALL ask the AI tutor anything about the question, at no cost, at most 15 messages a question and 40 a day. Before the full solution is revealed the tutor SHALL NOT give the answer or steps not yet revealed; after the check it SHALL explain the grade, the board and the solution. The class's teacher SHALL see the conversation.

#### Scenario: After the check
- **WHEN** a student asks "למה קיבלתי את הציון הזה?" after the check
- **THEN** the tutor answers with the board and the check's feedback in view
