# Spec Delta

## Purpose

Covers the photos teachers add to a lesson (exercises, theory explanations, other notes): who may add, see and remove them, and how a teacher chooses which ones students see.

## ADDED Requirements

### Requirement: Teacher chooses whether students see a resource
Every lesson resource SHALL have a visibility setting. When uploading, the setting SHALL default to visible for a theory explanation and hidden for an exercise or other photo. The teacher who added the resource, or a manager, SHALL be able to change it later. Resources that existed before this change SHALL start hidden.

#### Scenario: Upload a theory photo
- **WHEN** a teacher uploads a photo marked "הסבר תיאורטי" without changing the visibility box
- **THEN** the resource is visible to students

#### Scenario: Upload an exercise
- **WHEN** a teacher uploads a photo marked "תרגיל חדש" without changing the visibility box
- **THEN** the resource is hidden from students

#### Scenario: Another teacher tries to change visibility
- **WHEN** a teacher who did not add a resource, and is not a manager, tries to change its visibility
- **THEN** the server refuses and the setting does not change

#### Scenario: Existing resources
- **WHEN** this change is deployed
- **THEN** all resources added before it are hidden from students until a teacher makes them visible

### Requirement: Students see visible resources of their class's units
A signed-in student SHALL be able to list and open the visible resources of the units open to their class. Hidden resources, and resources of units not open to their class, MUST NOT be listed or served to them, and the response MUST NOT include storage paths.

#### Scenario: Skill sheet shows teacher explanations
- **WHEN** a student in a class with unit `t` opens skill `t_ext`, which has a visible resource tagged with it
- **THEN** the sheet shows it under "הסברים מהמורה", and tapping it shows the photo

#### Scenario: Unit list
- **WHEN** a unit has visible resources without a skill tag
- **THEN** the student sees them in the unit's "הסברים מהמורה" list

#### Scenario: Hidden resource requested directly
- **WHEN** a student requests the image of a hidden resource by its id
- **THEN** the server answers not found

#### Scenario: Unit not open to the class
- **WHEN** a student requests the resources of a unit their class does not have
- **THEN** the server answers with an empty list or not found, and no image is served

### Requirement: Teachers keep their current access
Accounts with the teacher role SHALL keep seeing all resources, hidden and visible, with the visibility shown on each. Only the teacher who added a resource, or a manager, SHALL be able to delete it.

#### Scenario: Teacher lists resources
- **WHEN** a teacher opens a unit's resources
- **THEN** they see every resource of the unit, each marked as visible to students or not
