# Design

## Context

- **The bank:** `mathly2/bank.py` builds one `Bank` from `content/math_algebra9.json` at start-up. It checks the file and caches its lookups. About 45 call sites read `app.state.bank`, and every learning feature works through it: the path, practice, mastery, quizzes, exercise tests, the simulation, review and grades.
- **Ids:** question keys are a skill id plus a hash of the question's content (`question_key`), so editing a question already gives it a new key. Answers, mastery, review and attempts store skill ids and question keys, not copies of the content.
- **Subjects today:** units already carry a `subject` name ("מתמטיקה"). The student's first screen already shows subject cards, with math hard-coded in `path.js` and `student.js` (`#/subject/math`).
- **Classes:** a class row stores a `lessons` list that is ignored: every class studies every lesson.
- **One server process** is assumed (status card, in-memory caches), so state held in the process is safe.
- **What can be reused:**
  - `pypdfium2` is already a dependency and renders PDF pages.
  - `pictures.py` stores private files in a Supabase bucket.
  - `ai.py` already calls Claude, maps failures to causes and records usage.
- **Migrations** are applied by hand in Supabase. The app must not fail to start if a migration is missing.

## Goals / Non-Goals

**Goals:**
- Lessons added at runtime behave exactly like math lessons, without touching the code paths that serve learning.
- Publishing takes effect without a restart or a redeploy (the Space rebuilds from GitHub, so content cannot live in the image).
- The AI never writes straight to students: everything passes the bank's own checks and a person's review.

**Non-Goals:**
- Splitting the daily goal, streak, comets or the readiness meter's history by subject: they stay shared across subjects.
- Geometry figures, graphs or images inside questions of new lessons.
- Math formulas from Word documents: equations made with Word's equation editor are not read in this change.
- Several server processes.

## Decisions

### 1. One merged `Bank`, swapped whole on publish
On start-up, and after each publish, unpublish or reorder, the server builds a new `Bank` from the math file plus every published lesson read from the database. It assigns it to `app.state.bank` in one step. Requests already running keep the bank they started with.
- *Why:* every existing feature keeps calling the same `Bank` API, and the start-up check runs on the merged content.
- *Alternative:* teach each feature to read two sources. That means ~45 call sites to change and test, with two code paths for the same behavior.

### 2. A lesson is one JSON document, stored twice: draft and published
New table `m2_lessons`, one row per lesson, with:
- `subject_id` and `position`;
- `draft` (jsonb, what the editor changes);
- `published` (jsonb or null, what students get);
- the worksheet's file references and the drafting status.

The document has the bank's own shape for one unit: lesson name, skills with questions and choices, and the mistakes they use. Publishing checks `draft` with the bank's checks and copies it to `published`. Unpublishing sets `published` to null.
- *Why:* the editor saves one document; the bank already knows how to check that shape; and "edit a published lesson" becomes edit the draft, then publish again.
- *Alternative:* normalized tables (skills, questions, choices, mistakes). That's many writes per edit, a large API, and checks split between SQL and Python for no gain at a school's scale.

### 3. Stable ids made by the server
- When a lesson is created, the server gives it a stable id, `w<n>` (`n` from the row's identity).
- Skills get `w<n>_<k>`, where `k` is a counter stored in the document, never reused, so deleting or reordering skills keeps the other ids.
- Mistakes are scoped to the lesson the same way (`w<n>_m<k>`).
- Question keys stay content hashes: an edited question is a new question (as the spec requires), and old answers keep pointing at the old key.
- The bank tolerates answers, review items and attempts whose question key no longer exists, as it does today for edited math questions.

### 4. Subjects table and class subjects
- **Subjects:** new table `m2_subjects` (`id` text, `name`, `icon`, `position`). It is seeded with `math`, which owns every unit of the file; the file's units get `subject_id = "math"` when loaded.
- **Class subjects:** `m2_classes` gets `subjects text[] not null default '{math}'`, so existing classes keep studying math. The ignored `lessons` column stays untouched.
- **A student's lessons:** published lessons of every subject of their classes. This is one helper that today's "every lesson" call sites switch to.
- **Routes:** student routes that list lessons (path, home, grades, collection) take the subject. Addresses become `#/subject/<id>`, and `#/subject/math` stays valid.

### 5. Tests belong to one subject
`m2_tests` gets `subject_id` (default `math`). Setting or changing a test checks that every lesson belongs to that subject. The countdown, exercise tests and the simulation already draw from the test's lessons, so only the home and test card filter by subject.

### 6. Drafting runs in the background with a status
- **Upload:** the upload stores the files, renders the pages, creates the lesson row with status `drafting`, and returns at once. A worker thread then calls the AI and writes the draft, or a failure cause.
- **Status:** the editor polls the status.
- **Restart:** a row left `drafting` by a restart becomes `failed: interrupted` on start-up and can be retried (as `ai_help.requeue_after_restart` does).
- *Why:* a drafting call can take a minute or more, longer than a request should hold.

### 7. Giving the worksheet to the AI
- **PDF:** sent to Claude as a document, so the text is read exactly, not from pictures.
- **Photos:** sent as images after the existing clean-up: re-encode, drop metadata.
- **Word:** text and embedded images are extracted with `python-docx` (new dependency) and sent as text plus images.

The prompt asks for a fixed JSON shape (the bank's unit shape plus a "from the sheet" or "written by AI" mark per question) via a tool definition, so the reply is structured, not parsed out of prose. The reply is checked; a reply that can't be parsed fails with the cause "an unusable answer", as `ai.py` already does.
- *Alternative:* convert Word to PDF with LibreOffice. That adds hundreds of MB to the image for a rare format.

### 8. Pages beside the editor
The worksheet is rendered to page images (PDF via `pypdfium2`, photos as they are, Word via its embedded images plus the text). The images are kept in a new private bucket `m2-worksheets` and served only to managers and developers, through the server, like answer pictures.

### 9. Subject-aware photo help
`ai_help` already sends the bank's skills to the AI so it can name the skill. It now sends only the skills of the subject of the skill the student was on, plus the subject's name. If no skill was given (a photo from home), it sends the skills of the subject whose home the student is on.

### 10. Who may do what
A new permission `content.manage` is held by manager and developer. It covers subjects, uploads, drafts, publishing and class subjects. It is added to `access.PERMISSIONS` and to the permission-matrix test.

## Risks / Trade-offs

- **The AI writes a wrong "right answer" or a misleading tip.** → Publishing needs a person's review. Questions are marked "from the sheet" or "written by AI" so reviewers check the AI's own first. A published lesson can be corrected at any time.
- **A slow or failed rebuild of the bank on publish.** → The new bank is built and checked before the swap; if building fails, the old bank stays and publishing reports the error. Building takes milliseconds at this size.
- **A missing migration at deploy.** → If the subjects or lessons tables are missing, start-up logs it and serves math from the file only. The content screens say the migration is needed. Nothing else breaks.
- **Hebrew right-to-left text and math symbols in AI output.** → Questions keep the bank's `$…$` formula convention, so the existing renderer applies. The editor previews each question as students will see it.
- **Cost of drafting.** → One call per upload (a retry is another). Usage is recorded under "worksheet". Only managers and developers can upload, and uploads are limited to 20 per person per day.
- **Shared daily goal and streak across subjects.** → Accepted for now (see Non-Goals): a science answer counts toward the same daily goal as math.

## Migration Plan

1. **Apply the migrations in Supabase**, all additive:
   - `m2_subjects`, with math seeded;
   - `m2_lessons`;
   - `m2_classes.subjects`, default `{math}`;
   - `m2_tests.subject_id`, default `math`;
   - the bucket `m2-worksheets`.

   Existing classes and tests keep working as math.
2. **Deploy stage 1:** subjects, database lessons and the JSON load. Students see no change until a non-math lesson is published and a class studies its subject.
3. **Deploy stage 2** (upload, AI draft, editor), then **stage 3** (publishing to classes, subject-aware help).

**Rollback:** unpublish the new lessons, or remove the subjects from classes. The code can be reverted and math still serves from the file. The added columns and tables are unused by the old code.

## Open Questions

- The fixed icon set for subjects (a handful of symbols such as ∑, ⚗, 🌍, 📖). This can be chosen during stage 1 without changing anything else.
- The exact daily upload limit per person (20 is a starting point).
