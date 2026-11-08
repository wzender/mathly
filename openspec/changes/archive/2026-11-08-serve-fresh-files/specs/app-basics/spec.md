## ADDED Requirements

### Requirement: Updates reach every device
After the app is updated, every device SHALL get the new page, styles and scripts the next time it opens the app, without the user clearing a cache. A file that did not change MAY still come from the device's cache once the server confirms it is unchanged.

#### Scenario: New look after an update
- **WHEN** the styles change on the server and a student who used the app before opens it again
- **THEN** the student sees the new styles without a forced reload

#### Scenario: Unchanged files
- **WHEN** a device asks again for a file that did not change
- **THEN** the server answers that it is unchanged and the device uses its saved copy

### Requirement: The app's icon
The app SHALL declare its icon (mathly1's, from `static/icons/`), so the browser tab shows it and the browser does not ask for a missing icon.

#### Scenario: Opening the app
- **WHEN** someone opens the app
- **THEN** the tab shows the app's icon and no request for an icon fails
