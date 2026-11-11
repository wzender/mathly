# Proposal

## Why

A developer has no way to see from the app whether the system is healthy, which version is running, or when it was last updated.

## What Changes

- **A status card on the developer's home** (`/api/dev/status`, developers only): an overall state, the running version (short commit), the date of the last update, when the server started, and a row per part (database, sign-in, question bank, AI help, phone notifications, answer pictures, hourly cleanup), with a "בדיקה מחדש" button.
- **The deployed version is known**: the Hugging Face sync writes `mathly2/version.json` (commit and date) in a commit made only for the Space; a local checkout reads git instead. The file is git-ignored.

## Capabilities

### New Capabilities
- `system-status`: the developer's status card (PRD DEV-5).

## Impact

- New `mathly2/status.py` and `mathly2/version.py`, `developer.js` and its styles, the sync workflow, the permission matrix (`dev.status`, no role lists it), PRD DEV-5. No database change.
