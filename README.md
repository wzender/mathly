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

Each class has one teacher, chosen from its students in the class editor (**ניהול → כיתות → עריכה → מורה הכיתה**). That account gets a **הכיתה שלי** button that opens the class report: for every other student, the skills finished in the class's units, the mistakes that keep coming back, the **בוחן מסכם** grade per unit, and the **מבחני תרגול** results, plus the mistakes most common across the class. Managers open the same report from a class's card (**מעקב**). The report reads the students' saved progress (`math_progress`) and Supabase's user list with the server's secret key; it needs no new migration. A student's numbers show up once they have signed in and practised on the current version of the app.

### The teacher's AI queue

Students never call the AI themselves. When a student saves an open answer (or hands in a **בוחן מסכם**, or sends a photographed problem), the request goes to their class teacher's **תור AI** instead of to Claude. The teacher sees each waiting request with the student's photo and the question, then presses **שליחה ל-AI** or **דחייה** (with an optional note for the student). The student's page shows the answer as waiting for the teacher, then the grade and feedback once it is sent, or the teacher's note if it was declined (the student can ask again). A failed send stays in the queue for the teacher to retry. Managers see every class's requests.

Accounts with the teacher, admin or developer role, and every class teacher, still send to the AI directly. A student can have at most 5 requests waiting; the daily limits on checks and photos still apply. A photographed problem is kept (as a clean JPEG) only until the teacher sends or declines it.

Apply [the additive queue migration](supabase/migrations/20261104090000_math_ai_requests.sql) before deploying this code: it adds the service-only `math_ai_requests` table. Without it, students cannot have answers checked (they see that checking is unavailable); teachers are not affected.

### Lesson resources (teachers)

A teacher taps a unit's title on the path (for example **טכניקה אלגברית 1**), photographs an exercise or an explanation, and saves it to that lesson's resources. Each photo is marked as **תרגיל חדש**, **הסבר תיאורטי**, or **אחר** (with a short free-text description), and can optionally name the topic it belongs to (for example **פילוג מורחב**). Apply [the additive resources migration](supabase/migrations/20261101090000_math_unit_resources.sql); it adds the `math_unit_resources` table and the private `mathly-resources` bucket. Only accounts with the teacher role see, add, or open resources, and only the teacher who added a photo (or a manager) can delete it. Students do not see resources yet.

Integration tests use bundled disposable PostgreSQL and local private test blobs, without project credentials or Docker:

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest tests/test_answer_scans.py tests/test_answer_grading.py tests/test_answer_browser.py
```

See [scan verification](docs/answer-scan-verification.md) for coverage and device checks.
