---
title: Mathly
emoji: 🧮
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Mathly

Mathly is a Hebrew ninth-grade algebra and geometry practice path. It contains 140 skills across 14 units that follow the Ministry of Education's 9th-grade teaching schedule (see `docs/prisa_9A.md`), ten per unit, immediate feedback for known mistakes, and optional photographed-problem help.

Geometry practice includes diagrams for rectangle area, triangle area, and Pythagoras.

Photographed problems are sent to the configured AI provider for solving and are not stored by Mathly.

When the computer asks for a photo of a handwritten answer, the student's phone can get a notification, even with the app closed. The phone offers it after its first photo is sent. It needs `VAPID_PRIVATE_KEY` (make one with `python -m app.push`) and the migration `supabase/migrations/20261103180000_math_push_subs.sql`. On an iPhone it works only from the app added to the home screen.

## User guide

The **?** button on the sign-in screen and in the app's header opens a short guide in Hebrew, with a tab for students and one for teachers. Its text is in `static/guide.js`; update it there when a feature changes.

## Science riddles (class vote)

The **מדעים** subject has a unit **חידות** with the skill **טיל**: the class guesses how much fuel a rocket needs. The teacher opens a vote and shows its 4-digit code; students join with the code on their own devices and vote. Votes stay hidden until the teacher presses check; the answer most students chose is launched, and the rocket flies, falls back (too little fuel) or stays on the pad (too heavy). A tie is not launched: students can change their vote and the teacher checks again. Riddles are in `app/science.json`. Votes live in the server's memory (the app runs as one process), so a restart ends the votes in progress. No sign-in or migration is needed.

## Run locally

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 7860
```

Open <http://localhost:7860>. Authentication is disabled when the Supabase values are empty.

## Configuration

Copy `.env.example` to `.env`. `ANTHROPIC_API_KEY` enables photographed-problem help. Supabase settings enable Google sign-in and math-class rosters.

For an existing deployment, back up Supabase and then run [docs/mathly-supabase.sql](docs/mathly-supabase.sql) in its SQL editor. The migration deliberately deletes the removed product's tables and non-math classes.

## Tests

```bash
venv/bin/python -m pytest
```

## Handwritten answers from a phone

Open-ended questions support handwritten calculations and drawings. On the computer, open the question and select **סריקת התשובה שלי בטלפון** (“Scan my answer with my phone”). Open the same site or installed Mathly PWA on your phone and sign in to the **same account**. Pending requests appear with the question and attempt identifier; choose one and confirm. Select **צילום התשובה**, allow the camera if asked, review the photograph, and use **צילום מחדש** to retake it before selecting **שליחת התשובה למחשב**. No image is uploaded before submission.

The computer shows waiting, uploading, answer received, upload failed, or request expired. After receipt, it displays the saved image on the original attempt, including after refresh. Receipt means the answer was saved; it does **not** award correctness or mark the skill mastered. When grading is available, checking starts automatically after the image is saved; the score and feedback appear on the original question. Existing multiple-choice practice and photographed-problem AI help remain separate.

Requests last **15 minutes**. A failed upload can be retried on the phone without taking another photo while that page remains open. An expired request offers **יצירת בקשת צילום חדשה** on either device; this keeps the attempt and invalidates the old request. A lost success response can safely be retried. Closing or refreshing the phone page discards an unsubmitted preview. If camera access is denied or capture is cancelled, retry the camera button and allow camera access in the site's browser settings. Camera behavior varies by platform; deploy over **HTTPS** and test on the phones you support.

### Enable private answer storage

1. Configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and the **server-only** `SUPABASE_SECRET_KEY` for the same project. Guest practice cannot initiate or access answer scans.
2. Apply [the additive answer-scan migration](supabase/migrations/20261031133254_math_answer_scans.sql) in that project's SQL editor or your normal migration pipeline. It adds three tables, ownership policies, a service-only transactional RPC, and the private `mathly-answers` bucket. **Do not rerun `docs/mathly-supabase.sql`**, which is the older destructive migration. Back up the target database before applying migrations.
3. Set `MATHLY_ANSWER_SCANS_ENABLED=1` and restart the app after the migration succeeds. The scan feature needs no AI key. With the flag off or credentials absent, scan APIs fail closed; guest practice and AI problem help still work.
4. Run `python -m app.answer_cleanup` hourly with the same server environment. It removes unreferenced private objects older than **24 hours** using the Storage API, including images orphaned by failed commits or account/attempt deletion. Referenced answers remain with their attempts; deleting an account/attempt cascades its records and cleanup removes the bytes after the grace period. The maintenance command continues to work when the student-facing feature flag is off. Monitor nonzero cleanup exit codes.
5. Optional: keep new answer images in a **private** Hugging Face storage bucket instead of Supabase Storage, so reading them back (to grade and to show them) is not Supabase egress. Set `MATHLY_ANSWER_BUCKET` (e.g. `wzender/mathly-answers`) and `HF_TOKEN` (a token that can write to it; on a Space, a secret). New images get file names starting with `hf-` and go to the bucket under `answers/`; images saved before stay in Supabase and are still read from there. Cleanup covers both: for the bucket it lists images older than 24 hours and removes the ones no answer uses. Never use a public bucket: these are students' answers.

Upload leases last at most **3 minutes**, bounded by request expiry. Interrupted leases become retryable failures on the next status/discovery check. Images are limited to 5 MB JPEG/PNG/WebP, decoded and re-encoded as JPEG to remove metadata, and accessed through owner-checked authenticated endpoints. When grading is configured, saving the image starts an automatic check using the saved image bytes and original question snapshot; the review screen explains this before submission. Private storage URLs are never sent. Upload receipt is independent of grading: an AI failure leaves the photograph saved and provides a retry option. The flow works across workers and server restarts.

### Check a handwritten answer

Apply [the additive grading migration](supabase/migrations/20261031193200_math_answer_grading.sql) **after** the answer-scan migration and **before** deploying the grading code. It adds a private grading table and service-only RPC; it preserves existing classes, attempts, and photographs. Configure the server's `ANTHROPIC_API_KEY` (or the existing `CLAUDE_API_KEY` alias); the grader uses `MATH_MODEL` or the same default model as photographed-problem help. Without that key, photographs remain usable and the UI explains that grading is unavailable. If the grading migration has not yet been applied, photo receipt and viewing remain available, with grading hidden.

After a photograph is received, grading starts automatically on the server, even if the computer is closed. The phone confirms upload immediately while the computer displays **בודקים את התשובה…** until feedback is ready. Reopening a saved, never-checked attempt starts its first check automatically as well; no separate grading click is required. The phone review screen explains before submission that the photograph is sent to AI for checking. The grader evaluates the original question, mathematical result, reasoning, required drawing, units, and completeness. It returns Hebrew feedback, a score out of 100 where the work can be assessed, a next step, a transcription you can check, and an expandable worked solution. Unreadable or uncertain work receives no score and never completes the skill. A correct, complete solution completes the skill in the current account's device-local progress; receiving the image alone still does not. AI grading can make mistakes; the feedback panel identifies it as automatic and shows the transcription for review.

Checks and feedback are stored privately against the original attempt and photo, surviving refresh and server restarts. Repeated clicks or a lost response reuse a running/completed check. A failed check can be retried explicitly with **ניסיון בדיקה נוסף**, keeping the image. Automatic discovery and duplicate uploads never retry a failed check or consume its allowance repeatedly. Interrupted checks become retryable after **5 minutes**. Each account can start **20 checks per Jerusalem calendar day**, including failed checks, with at most two running simultaneously. Completed checks remain readable without another AI call or daily charge. Select **ניסיון חדש וצילום מחדש** to create a fresh attempt and send a corrected or clearer photograph; the previous attempt, photo, and feedback remain stored.

For rollback, turn `MATHLY_ANSWER_SCANS_ENABLED` off and restart; preserve the new tables and private bucket. The skills API serves the original multiple-choice geometry sample while scanning is disabled, including for guest practice and older frontends. Enabling scanning again restores open-ended presentation and access to saved answers. Keep stored answer records for recovery. No destructive down migration is needed.

### Class teacher

Each class has one teacher, chosen from its students in the class editor (**ניהול → כיתות → עריכה → מורה הכיתה**). That account gets a **הכיתה שלי** button that opens the class report: for every other student, the skills finished in the class's units, the mistakes that keep coming back, the **בוחן מסכם** grade per unit, and the **מבחני תרגול** results, plus the mistakes most common across the class. Managers open the same report from a class's card (**מעקב**). The report reads the students' saved progress (`math_progress`) and Supabase's user list with the server's secret key. A student's numbers show up once they have signed in and practised on the current version of the app.

The report opens with **דורשים תשומת לב**: the students who have not practised for 7 days, are stuck on a skill (3 or more wrong answers in 14 days without finishing it), practised less than half as much this week as last (from Sunday, and only when last week had at least 10 right answers), have a unit-quiz grade below 55, or have not started. Each is listed with the reasons. The **טבלת מיומנויות** view is a grid of students by skill for a chosen unit (or by unit), with how many finished each skill and a ⚠ on skills where at least a third of the students are practising without having finished. The list can be sorted by attention, name, progress or last activity; the choices are kept on the teacher's device. Students are shown by the class nickname, else their Google name, else the start of their email. The thresholds are constants at the top of the teacher's signals in `static/math-sky.js`. These signals come from the device-reported practice data below, so they tell the teacher where to look; they are not grades.

**What the report can be trusted for.** Progress is kept by the student's device, so skills finished, gold stars and practice-exam results are only what the device reports; the report labels them **נתוני תרגול מהמכשיר**. The **בוחן מסכם** grade is different: when a student hands a quiz in, the server stores the sitting (`math_quiz_sittings`) and works the grade out itself from the stored checks and the quiz's points (`app/quiz_grades.py`), so a score edited in the browser changes nothing. A sitting has no grade while any photographed answer still waits for its check (the report says **ממתין לבדיקה**); a question without a photo earns 0. Submissions from before this was deployed exist only on the student's device and show as **לא מאומת**, with no grade. Apply [the sittings migration](supabase/migrations/20261104120000_math_quiz_sittings.sql) (after the answer-scan and grading migrations) before deploying this code. Without it, handing a quiz in fails with "quiz sittings unavailable" and the report shows no quiz grades.

### Assignments

The class teacher (or a manager) gives the class an **assignment** from the class report's **משימות** tab (`app/assignments.py`, table `math_assignments`): a title, a note, a due date and 1 to 20 items, each a skill to finish, a unit quiz to hand in, or a practice exam over chosen units. Every item must belong to the units open to the class; the same item twice is kept once. Students see their classes' assignments in a **משימות מהמורה** card on the home screen (`GET /api/math/assignments`, without the teacher's email), a continue button that opens the first item not done (a practice exam opens with its units chosen), and a 📌 on the path's stars of skills in unfinished assignments. Finished ones stay in a **הושלמו** list for two weeks after the due date.

Nothing about completion is stored: the page works it out (`assignmentState` in `static/math-sky.js`), the same way for the student and for the teacher's report. A skill is done when it is finished, whenever that was; a unit quiz when the server has a sitting of it handed in after the assignment was made (`app/quiz_grades.py`); a practice exam when one covering all the item's units was taken after that. Dates are Jerusalem days, so an item done on the due date is on time. The report's tab shows how many students finished each assignment and, per student, which items are done, late (✓ באיחור) or missing; a student with an unfinished assignment past its due date is added to **דורשים תשומת לב**. The completion of skills and practice exams is what the student's device reports, like the rest of the practice data.

Apply [the assignments migration](supabase/migrations/20261104210000_math_assignments.sql) before deploying: it adds the service-only table, which is deleted with its class. Without it the routes answer 503, students see no card, and the report's tab says assignments are unavailable.

### Reviewing answers (teacher score and comment)

The class teacher (or a manager) can open any open answer of their students that has a saved photo: from the **פתיחה** button in the class report's unit-quiz table (it lists the latest sitting's answers), or from a handled answer in the AI queue. The page shows the question, the photo, the automatic check and a form for a **score** (0 to 100), a **comment**, or both (`app/teacher_review.py`, table `math_teacher_reviews`). The automatic check is never edited: the review is kept next to it, the newest review of an answer counts and older ones stay as history. Wherever an answer's score is used, the teacher's wins (`effective_score`): the unit-quiz grade (`app/quiz_grades.py`) and the skill itself, which a teacher score of 100 completes on the student's device the next time they open the answer. A teacher can also score an answer the AI could not read or has not yet checked. The student sees **הערת המורה** and its score above the automatic check, which stays visible and labelled, and a notice on the home screen until they open the answer. A student can press **לבקש מהמורה לבדוק שוב** on a checked answer with a short message: one open request per answer and five per student (`math_review_requests`). Requests appear in the AI queue's **בקשות לבדיקה חוזרת** tab (counted on the queue button) and on the student's report card, and saving a review closes the request. Only the teacher of the student's class, or a manager, can open or review the answer; anyone else gets a 403 and no image or check.

Apply [the reviews migration](supabase/migrations/20261104150000_math_teacher_reviews.sql) after the quiz-sittings migration and before deploying this code. It adds the two tables and two service-only functions, and replaces `math_quiz_sitting_json` so a sitting's grade can use the teacher's score. Without it the teacher's review routes answer 503, and students see their answers and grades as before, with no teacher section.

### The teacher's AI queue

Students never call the AI themselves. When a student saves an open answer (or hands in a **בוחן מסכם**, or sends a photographed problem), the request goes to their class teacher's **תור AI** instead of to Claude. The teacher sees each waiting request with the student's photo and the question, then presses **שליחה ל-AI** or **דחייה** (with an optional note for the student). The student's page shows the answer as waiting for the teacher, then the grade and feedback once it is sent, or the teacher's note if it was declined (the student can ask again). A failed send stays in the queue for the teacher to retry. Managers see every class's requests.

Accounts with the teacher, admin or developer role, and every class teacher, still send to the AI directly. A student can have at most 5 requests waiting; the daily limits on checks and photos still apply. A photographed problem is kept (as a clean JPEG) only until the teacher sends or declines it.

Apply [the additive queue migration](supabase/migrations/20261104090000_math_ai_requests.sql) before deploying this code: it adds the service-only `math_ai_requests` table. Without it, students cannot have answers checked (they see that checking is unavailable); teachers are not affected.

### Worked examples (help when stuck)

A skill in `app/math_algebra9.json` may have an `example`: a question of its own (never one of the skill's practice questions), `steps` of `{do, why}`, and the `answer`. The **?** button in a skill's sheet opens it over the question, one step at a time; it is also offered after the second wrong answer in a round. Opening it is kept in the student's progress (`examples`: count and last time, merged across devices), changes nothing about finishing or gold, and shows on the student's report card for two weeks. Students never call the AI, so examples are written in advance and **a math teacher must review every one before it reaches students**. `app/math_skills.py` refuses data whose examples are malformed or copy a practice question, and `skills_without_example(graph)` lists what is still to write.

`scripts/draft_examples.py` helps write them: `draft --unit t` asks Claude for one example per skill of a unit that has none (one request per skill, using `ANTHROPIC_API_KEY` and `MATH_MODEL`; `--dry-run` shows what it would send) and writes a review file under `docs/example-drafts/` without touching the data. The teacher edits the file, sets `approved` and `reviewed_by` on the good ones, and `merge docs/example-drafts/t.json` adds only those to the data file after the app's own checks.

### Lesson resources (teachers)

A teacher taps a unit's title on the path (for example **טכניקה אלגברית 1**), photographs an exercise or an explanation, and saves it to that lesson's resources. Each photo is marked as **תרגיל חדש**, **הסבר תיאורטי**, or **אחר** (with a short free-text description), and can optionally name the topic it belongs to (for example **פילוג מורחב**). Apply [the additive resources migration](supabase/migrations/20261101090000_math_unit_resources.sql); it adds the `math_unit_resources` table and the private `mathly-resources` bucket. Only accounts with the teacher role see, add, or open all resources, and only the teacher who added a photo (or a manager) can delete it or change who sees it.

**Showing resources to students.** Each resource has a **גלוי לתלמידים** box: checked by default for a theory explanation, unchecked for an exercise or a note, and changeable later by its teacher or a manager (`PATCH /api/math/resources/{id}`). Students see the visible resources of the units open to their class (`/api/math/units/{unit}/student-resources`, with no teacher email and no storage path; hidden ones and other classes' units answer 404). A resource tied to a skill shows in that skill's sheet and its **?** help panel under **הסברים מהמורה**; the unit's other visible resources are on a list opened from a button under the unit. Apply [the visibility migration](supabase/migrations/20261104180000_math_resources_visible.sql); it adds the `visible` column, and every resource added before it starts hidden. Without it, uploads still work (the box is ignored) and students see none.

Integration tests use bundled disposable PostgreSQL and local private test blobs, without project credentials or Docker:

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest tests/test_answer_scans.py tests/test_answer_grading.py tests/test_answer_browser.py
```

See [scan verification](docs/answer-scan-verification.md) for coverage and device checks.
