# Tasks

## 1. Data (stage 1)

- [x] 1.1 Add migrations: `m2_subjects` (seeded with math), `m2_lessons` (subject, position, draft, published, drafting status, worksheet files), `m2_classes.subjects` (default `{math}`), `m2_tests.subject_id` (default `math`), server-only grants, and the private bucket `m2-worksheets` (made by the server when first needed, as `m2-answers` is, not by the migration). Verify on a local PostgreSQL that all migrations apply in order, that existing classes and tests read as math, and that the browser roles are refused (`test_migrations.py`).
- [x] 1.2 Add the store methods for subjects, lessons (draft and published), class subjects and a test's subject, in both `InMemoryStore` and `SupabaseStore`; add the new reads and changes to `cached.py`. Verify with store tests for each method, including a missing table reported as unavailable.
- [x] 1.3 Add the `content.manage` permission for manager and developer in `access.py`. Verify that the permission-matrix test covers every new route.

## 2. Merged bank (stage 1)

- [x] 2.1 Give the file's units `subject_id = "math"` and teach `Bank` to take extra units from published lessons, with the same checks. A broken published lesson is left out and logged; a broken file still stops start-up. Verify with bank tests: merged lessons in subject order, a broken database lesson skipped, a broken file refused.
- [x] 2.2 Build the bank from the file plus published lessons at start-up, and rebuild and swap `app.state.bank` after publish, unpublish and reorder. If the tables are missing, log it and serve the file only. Verify with tests: a published lesson appears without a restart, a failed build keeps the old bank, and start-up works without the migration.
- [x] 2.3 Give server-made ids to lessons, skills and mistakes (`w<n>`, `w<n>_<k>`, `w<n>_m<k>`), never reused within a lesson. Verify with tests: deleting a skill keeps the others' ids, and mastery and review survive a reorder.

## 3. Subjects and classes (stage 1)

- [x] 3.1 Add the subject routes: list, create, rename and change icon, delete an empty subject, and reorder a subject's lessons. Verify with API tests: unique names ignoring case, 403 for a teacher, deleting a subject with lessons refused.
- [x] 3.2 Add a developer route that loads a lesson as JSON in the bank's unit shape into a subject as a draft. Verify with an API test that loads a sample science lesson and that a malformed one is refused with the checks' messages.
- [x] 3.3 Add the subjects tab to the manager screen: the list, create, rename and icon, and lesson order. Verify with a Playwright test on a phone and a desktop.
- [x] 3.4 Add the subject choice to the class editor (math ticked by default), and store and return a class's subjects. Verify with API and Playwright tests: a new class studies math, adding and removing a subject, and progress kept after removing one.
- [x] 3.5 Make a student's lessons the published lessons of their classes' subjects, through one helper used by every "every lesson" call site. Verify that the existing access and path tests still pass and a new test covers two classes with two subjects.
- [x] 3.6 Update the PRD (subjects, CLS rules) and the `subjects`, `exercise-bank` and `accounts-and-classes` spec deltas if behavior moved during implementation. Verify that `openspec validate add-subjects-and-worksheets --strict` passes.

## 4. Per-subject student screens (stage 1)

- [ ] 4.1 Show a card per subject on the first screen, in subject order with math first, each counting only its skills; route `#/subject/<id>` keeps `#/subject/math` working, and `#/skill/<id>` opens its subject's path. Verify with Playwright tests for one subject and for two subjects.
- [ ] 4.2 Filter the path, the next skill, the home, grades and the collection by the open subject. Verify with API tests: another subject's lessons are absent, and the owl stays in its subject.
- [ ] 4.3 Give tests a subject: the test form picks a subject the class studies and only its lessons, and the server refuses lessons of two subjects. The home and test card show only the open subject's tests. Verify with API and Playwright tests.
- [ ] 4.4 Group the curriculum tab by subject. Verify with a Playwright test with two subjects.
- [ ] 4.5 Check practice, mastery, the lesson quiz, the review list, exercise tests, the simulation and grades end to end on a lesson loaded by JSON in a second subject. Verify with one journey test, API plus browser.

## 5. Worksheet upload and AI draft (stage 2)

- [ ] 5.1 Add the upload route for managers and developers. It accepts one PDF (≤ 20 pages), 1–10 photos or one .docx, up to 15 MB, for an existing or a new subject; renders the pages to images in `m2-worksheets`; and creates a lesson with status `drafting`. Add `python-docx` to the requirements. Verify with API tests: each format, a refused spreadsheet, 403 for a teacher, the 20-a-day limit.
- [ ] 5.2 Add the drafting call to `ai.py`. PDFs go as a document, photos as images, Word as text plus images. The reply is a fixed tool schema (the unit shape plus a source mark per question), with 8–12 questions per skill. It is given only the pages and the subject's name, and usage is recorded as "worksheet". Verify with tests using a fake AI client: the request carries no person's or class's name, a malformed reply fails as "an unusable answer", and the usage record is written.
- [ ] 5.3 Run drafting in a background worker that writes the draft or the failure cause. Rows left `drafting` by a restart become retryable failures, and retrying needs no new upload. Verify with tests for success, each failure cause in words, retry, and recovery after a restart.

## 6. The draft editor (stage 2)

- [ ] 6.1 Add the draft routes: read, and save the whole document. Saving checks the shape, not completeness. Verify with API tests: save and read back, and 403 for others.
- [ ] 6.2 Build the editor screen:
  - the worksheet's pages beside the draft;
  - the lesson's name;
  - skills, questions, choices, the right choice and mistakes, with add, delete and reorder;
  - each question's source mark;
  - a preview of each question as students see it;
  - every change saved.

  Verify with Playwright tests: fixing a right answer survives leaving and coming back, an added question is marked as written by a person, and no sideways scroll on a phone.
- [ ] 6.3 Show the drafting status and failures on the editor, with "נסו שוב". Verify with a Playwright test with a fake AI that first fails, then succeeds.
- [ ] 6.4 Update the PRD and the `worksheet-lessons` spec delta if behavior moved. Verify that `openspec validate add-subjects-and-worksheets --strict` passes.

## 7. Publishing and subject-aware help (stage 3)

- [ ] 7.1 Add publishing:
  - run the checks: a name, at least one skill, ≥ 5 questions per skill, one right choice, and a mistake with a name and a tip for every wrong choice;
  - list every problem and where it is;
  - copy the draft to published, last in the subject;
  - rebuild the bank.

  Verify with API tests: each failing check named, and a published lesson on a studying student's path without a restart.
- [ ] 7.2 Add editing a published lesson (edit the draft, publish again) and unpublishing, which is refused while a coming test covers the lesson. Verify with API tests: an edited question gets a new key and old answers are kept, unpublishing hides the lesson and keeps progress, and the coming-test refusal names the test.
- [ ] 7.3 Make photo help subject-aware: send the subject's name and only its skills; if no skill was given, use the subject of the home the student is on. Verify with tests using a fake AI client: a science photo's request holds science skills only, and the named skill must belong to that subject.
- [ ] 7.4 Update the PRD (AI help, real tests, curriculum) and the remaining spec deltas. Verify that `openspec validate add-subjects-and-worksheets --strict` passes.

## 8. Integration

- [ ] 8.1 Run one full journey with a fake AI client: a manager uploads a worksheet for a new subject, edits the draft, publishes, and adds the subject to a class; a student of the class practises, masters a skill and takes the quiz; the teacher sets a test in the new subject. Verify that the journey test passes and the full `mathly2/tests` suite passes.

## Workflow follow-up

- Apply the new migrations in Supabase before deploying stage 1.
- Archive the change after the project's review requirements are satisfied, and verify the archived specs.
