# Tasks

## 1. Scaffold

- [x] 1.1 Create the `mathly2/` package with `main.py`, `config.py` and a `GET /api/health` endpoint; verify `venv/bin/python -m uvicorn mathly2.main:app --port 7861` answers `{"ok": true}`
- [x] 1.2 Add `mathly2/requirements.txt` (and dev requirements) and a `mathly2/tests/` pytest setup; verify `venv/bin/python -m pytest mathly2/tests` runs and passes a health test
- [x] 1.3 Add `clock.py` (server time, Israel calendar day) with tests for a time just before and just after midnight in Asia/Jerusalem; verify the tests pass

## 2. App shell: Hebrew, right-to-left, phone first

- [x] 2.1 Serve `static/index.html` (`lang="he"`, `dir="rtl"`), `app.css` with light/dark tokens and a phone-first layout, and `app.js`; verify a Playwright test at 390px width finds `dir="rtl"` and no horizontal scroll
- [x] 2.2 Document how to run the new app locally in `mathly2/README.md`; verify the documented commands start it

## 3. Exercise bank

- [x] 3.1 Copy `app/math_algebra9.json` to `mathly2/content/` and add `bank.py`, which loads and checks it (unique ids, one correct choice per question, every `mistake` and `back` id exists, every skill's lesson exists); verify tests pass on the real bank and fail on broken samples
- [x] 3.2 Add `GET /api/lessons` (lessons with their skills, no questions); verify a test returns 24 lessons and 96 skills
- [x] 3.3 Copy `math-tex.js` and its MathJax setup into `mathly2/static/` and show every `$…$` as a formula; verify a Playwright test shows `$x² − 2x − 15$` as a rendered formula
- [x] 3.4 Add `scripts/content_gaps.py` that lists skills without a worked example, faded examples or "why this step?" choices, lessons without a quiz, and skills with too few questions; verify it runs on the bank and lists the skill with no questions

## 4. Sign-in and classes

- [x] 4.1 Add the migration `mathly2/supabase/migrations/…_m2_classes.sql` (`m2_classes`, `m2_class_members` with unique email, row-level security on with no anon or authenticated policies); verify a pgserver test applies it and an authenticated-role insert is refused
- [x] 4.2 Add `store.py` (Supabase REST using the secret key) and `InMemoryStore` with the same interface; verify the class tests pass against `InMemoryStore`
- [x] 4.3 Add sign-in: Google through Supabase in the browser, token checked by the server, teachers from `TEACHER_EMAILS`, and the dev email sign-in when Supabase is not set; verify tests for teacher, student and no-token requests
- [x] 4.4 Add the teacher's class endpoints and screen: create a class, list classes, add students by pasted emails, remove a student, with a clear message when a student is already in another class; verify API tests and a Playwright test adding 3 emails
- [x] 4.5 Link a student's account to their class membership on first sign-in, and show the "ask your teacher to add you" message, with their email, when they are in no class; verify tests for both cases
- [x] 4.6 Verify no student content is served before sign-in: a test calls every `/api/` endpoint without a token and gets 401 (except health)

## 5. Deployment

- [x] 5.1 Add `mathly2/Dockerfile` (same base as the current one, `uvicorn mathly2.main:app`) and document the settings it needs in `mathly2/README.md`; verify `docker build -f mathly2/Dockerfile .` succeeds and the container answers `/api/health`

## Workflow follow-up

- Archive this change once it is deployed and reviewed, so `app-basics`, `exercise-bank` and `accounts-and-classes` move into `openspec/specs/`.
