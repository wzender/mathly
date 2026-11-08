# Tasks

## 1. Fresh files

- [x] 1.1 Send `Cache-Control: no-cache` with the app page and every file under `/static`, keeping the ETag; verify tests that the page and a static file carry the header, that a repeat request with the file's ETag gets 304, and that the API routes are unchanged
- [x] 1.3 Copy mathly1's `static/icons/` into `mathly2/static/icons/` unchanged and link `icon-192.png` from the page; verify a Playwright test that the page loads with no failed request and no console error, and that the icon file is served
- [x] 1.2 Add the line to the PRD's notes for the build; verify `openspec validate serve-fresh-files --strict` and the mathly2 tests pass
