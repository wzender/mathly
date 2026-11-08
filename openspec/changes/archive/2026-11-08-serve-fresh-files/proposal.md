# Proposal

## Why

After an update, a browser can keep showing the app's old look: the server sends its page, styles and scripts with no caching instruction, so the browser may reuse a saved copy without asking. This happened with the always-dark sky (a white background until a forced reload), and it would happen to students' phones after every update.

## What Changes

- The server tells the browser to check with it before reusing the app page and its files (`Cache-Control: no-cache`), so an unchanged file still comes from the cache (the server answers "not modified") and a changed one is fetched.
- The page declares mathly1's icon, so the tab shows it and the browser's request for a missing `/favicon.ico` (an error in the console) stops.
- Two new requirements in `app-basics`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `app-basics`: adds "Updates reach every device" and "The app's icon".

## Impact

- `mathly2/main.py` (the page and `/static`); the API routes are unchanged.
- PRD 7.3 notes for the build gets one line.
