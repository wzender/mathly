# Proposal

## Why

Mathly teaches one subject, ninth-grade math, from one content file baked into the app. A school that wants a second subject, or another lesson in it, needs a developer to write the content by hand. The subjects screen already exists, but it can only ever show math. Managers have worksheets for other subjects, and the AI the app already uses for photo help can turn a worksheet into the multiple-choice skills, questions and mistakes that drive the whole path.

## What Changes

- **Subjects become real.** A subject has a name, an icon and its lessons. Math is the first subject, unchanged for current users. A manager or a developer can create a new subject and rename it.
- **Lessons can live in the database.** Lessons of new subjects (and new lessons of any subject) are stored in Supabase, as lessons → skills → questions → mistakes. The server merges them with the math content file, so the path, practice, mastery, the quiz, the review list, real tests, exercise tests, the simulation and the grades work for them unchanged.
- **Classes study subjects.** A class chooses which subjects it studies, math by default, and studies every published lesson of those subjects. **BREAKING** for the rule "every class studies every lesson of the bank": a class that does not study a subject does not see its lessons.
- **Students get a card per subject.** The subjects screen shows a card for each subject of the student's classes, and each subject has its own home, path and grades. Tests and the countdown belong to one subject.
- **Worksheet → lesson.** A manager or a developer uploads a worksheet (PDF, a photo or a Word document) and picks a new or existing subject. The AI drafts one lesson from it: its skills; about ten multiple-choice questions per skill (the sheet's own questions and similar new ones); for each wrong choice, a named mistake with a tip.
- **Review before anything reaches a student.** The draft opens in an editor where every part can be changed, added or deleted. Publishing is refused until the lesson passes the same checks the math file passes on start-up (one right answer, every wrong choice names an existing mistake, enough questions per skill). A published lesson can be edited later. Unpublishing it hides it from the path and keeps everyone's progress.
- **Subject-aware photo help.** The AI photo help is told the subject and that subject's skills, so it names the right skill and does not assume math.
- **Staged delivery.** (1) Subjects and lessons in the database, which a developer can load as JSON. (2) Worksheet upload, AI draft and the editor. (3) Publishing into classes and subject-aware AI help.

## Capabilities

### New Capabilities
- `subjects`: what a subject is, who creates and renames it, which classes study it, and how its lessons are ordered and published.
- `worksheet-lessons`: uploading a worksheet, the AI's draft of a lesson from it, the editor, the checks before publishing, publishing, editing and unpublishing a lesson.

### Modified Capabilities
- `exercise-bank`: lessons, skills, questions and mistakes come from the math content file and from lessons published in the database; the start-up check applies to both, and a lesson is checked again when it is published.
- `accounts-and-classes`: a class studies the subjects it chooses (math by default) and every published lesson of them, instead of every lesson of the bank.
- `learning-path`: the subjects screen shows a card per subject of the student's classes; the path, the next skill and the counts are per subject.
- `real-tests`: a test covers lessons of one subject only.
- `curriculum`: the curriculum tab lists the lessons by subject.
- `ai-help`: photo help is given the subject and its skills, and names a skill of that subject.

## Impact

- **Database:** new Supabase tables for subjects, published lessons and their content, worksheet drafts, and the subjects each class studies (new migrations, applied by hand as today). Files go to a private storage bucket, like answer pictures.
- **Server:** `bank.py` stops being file-only and loads published lessons too, reloading when one is published. New routes for subjects, uploads, drafts, publishing and class subjects. `skills.py`, `quizzes.py`, `realtests.py`, `review.py` and `progress.py` filter by subject where they list lessons. `ai.py` gets a worksheet-drafting call and subject-aware photo help.
- **Screens:** the manager's screen gets a subjects tab with the upload and the draft editor. The class editor gets the subject choice, and the student's subject cards and routes become per subject (`#/subject/<id>`).
- **Cost:** each worksheet draft is one or more paid AI calls, recorded with the existing usage records.
- **Dependencies:** reading a Word document needs a document-reading library; PDFs reuse the page rendering mathly1 has.
- **Not in this change:** open questions answered by photo, geometry figures and graphs for new lessons, and teachers uploading for their own classes.
