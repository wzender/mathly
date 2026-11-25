## Why

The new home looked crowded and its buttons were not distinct, and a phone that kept the app open drew the new screens with the old styles.

## What Changes

- A design review's hierarchy: one gold primary action; closing the gaps as a quiet catch-up card; neutral quick-practice and photo tiles; three blocks 16px apart; plain status items; a one-line current-lesson row; a one-row header on phones.
- The page loads its files with the build's version; every answer carries `X-Mathly-Build`; an app left open after an update reloads at the next change of screen.

## Impact

`mathly2/static/app.css`, `mathly2/static/home.js`, `mathly2/static/app.js`, `mathly2/static/api.js`, `mathly2/static/index.html`, `mathly2/main.py`. No migration.
