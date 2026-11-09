## ADDED Requirements

### Requirement: A button that takes time shows it
When an action started by a button or a form's submit takes longer than about a third of a second, the button SHALL show that it is working (a spinner) and SHALL ignore another press, until the action ends. This applies to every such button in the app. The indicator MUST NOT depend on motion: with reduced motion the button shows "…" instead of a turning spinner.

#### Scenario: A slow save
- **WHEN** a person presses a button and the server takes two seconds
- **THEN** after about a third of a second the button shows a spinner and a second press does nothing, and it returns to normal when the answer arrives

#### Scenario: A quick action
- **WHEN** the server answers within a tenth of a second
- **THEN** the button never shows the spinner

#### Scenario: Reduced motion
- **WHEN** the device asks for reduced motion and an action is slow
- **THEN** the button shows "…" and nothing turns
