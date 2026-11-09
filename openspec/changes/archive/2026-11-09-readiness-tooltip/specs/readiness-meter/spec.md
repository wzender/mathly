## ADDED Requirements

### Requirement: The number explains itself
Beside the readiness number there SHALL be an info button that shows a short tooltip: that the number is made of mastery (50%), practice tests (20%) and the simulation (30%), that a part with no grade yet is left out, and that without the simulation the number cannot pass 80. The tooltip SHALL open on hover, on focus and on tap, SHALL close on a second tap, a tap elsewhere or Escape, and the button SHALL have an accessible name.

#### Scenario: Hover or tap
- **WHEN** a student hovers over or taps the info button
- **THEN** the tooltip with the three lines shows

#### Scenario: Closing
- **WHEN** the tooltip is open and the student presses Escape or taps elsewhere
- **THEN** it closes

#### Scenario: On a phone
- **WHEN** the tooltip is open on a 360px screen
- **THEN** it fits the screen and the page does not scroll sideways
