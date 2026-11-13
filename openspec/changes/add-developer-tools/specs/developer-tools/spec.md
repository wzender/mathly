# Spec Delta

## Purpose

Tools only developers can reach: a lab for testing tools, and a view of what the AI costs.

## ADDED Requirements

### Requirement: Developers only
The lab and the AI usage page SHALL be reachable only by developers.

#### Scenario: Manager
- **WHEN** a manager asks for the lab
- **THEN** it is refused

### Requirement: Lab
The lab SHALL be a page for testing and development tools. Until the first tool is chosen it SHALL say that tools will be added here.

#### Scenario: Empty lab
- **WHEN** a developer opens the lab
- **THEN** it says tools will be added here

### Requirement: AI usage
A page SHALL show the AI's calls and estimated cost by day, by class and by kind of call.

#### Scenario: One week
- **WHEN** a developer opens the usage page
- **THEN** it shows each day's calls and cost, with totals per class and per kind
