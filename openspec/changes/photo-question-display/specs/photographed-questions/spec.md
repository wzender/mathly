## ADDED Requirements

### Requirement: Math from the AI is shown as plain symbols
The system SHALL show the question, answer, steps, feedback and tutor messages of a photographed question with LaTeX commands replaced by plain symbols (\triangle as △, \angle as ∠, \perp as ⊥, ^\circ as °, \frac{a}{b} as a/b, \text{…} as its text, subscripts and superscripts as ₁ ²) and an empty "()" removed, also for questions kept before this change.

#### Scenario: A question read with LaTeX
- **WHEN** the AI reads "\triangle ABC …, \angle A_1 = 30^\circ, PC = 18\text{ ס"מ}"
- **THEN** the student sees "△ ABC …, ∠ A₁ = 30°, PC = 18 ס"מ" and no backslash

### Requirement: The photo is shown with the question
The system SHALL show the photographed picture open above the question (at most 30% of the screen high), enlarge it on a tap, and let the student hide it.

#### Scenario: Comparing with the photo
- **WHEN** a photographed question is ready
- **THEN** its photo is visible above the question and a tap on it shows it at full width
