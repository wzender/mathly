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

Mathly is a Hebrew ninth-grade algebra and geometry practice path. It contains 59 skills across seven units, immediate feedback for known mistakes, and optional photographed-problem help.

Choose **צילום בטלפון, פתרון במחשב** on the computer, scan the QR code with your phone, take a photo, and confirm sending it. The answer and worked solution appear automatically on the computer. Links last 15 minutes and accept one exercise; the phone does not need a separate login. Geometry practice includes diagrams for rectangle area, triangle area, and Pythagoras.

Both devices must be able to reach the same app URL. For local use, open the computer's LAN address (for example `http://192.168.1.10:7860`) on both devices instead of `localhost`. Phone links and results are temporary in server memory: use a single server worker; restarting it clears active links. Images are sent to the configured AI provider for solving and are not stored by Mathly.

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

The computer shows waiting, uploading, answer received, upload failed, or request expired. After receipt, it displays the saved image on the original attempt, including after refresh. Receipt means the answer was saved; it does **not** award correctness or mark the skill mastered. Existing multiple-choice practice and photographed-problem AI help remain separate.

Requests last **15 minutes**. A failed upload can be retried on the phone without taking another photo while that page remains open. An expired request offers **יצירת בקשת צילום חדשה** on either device; this keeps the attempt and invalidates the old request. A lost success response can safely be retried. Closing or refreshing the phone page discards an unsubmitted preview. If camera access is denied or capture is cancelled, retry the camera button and allow camera access in the site's browser settings. Camera behavior varies by platform; deploy over **HTTPS** and test on the phones you support.

### Enable private answer storage

1. Configure `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and the **server-only** `SUPABASE_SECRET_KEY` for the same project. Guest practice cannot initiate or access answer scans.
2. Apply [the additive answer-scan migration](supabase/migrations/20261031133254_math_answer_scans.sql) in that project's SQL editor or your normal migration pipeline. It adds three tables, ownership policies, a service-only transactional RPC, and the private `mathly-answers` bucket. **Do not rerun `docs/mathly-supabase.sql`**, which is the older destructive migration. Back up the target database before applying migrations.
3. Set `MATHLY_ANSWER_SCANS_ENABLED=1` and restart the app after the migration succeeds. The scan feature needs no AI key. With the flag off or credentials absent, scan APIs fail closed; guest practice and AI problem help still work.
4. Run `python -m app.answer_cleanup` hourly with the same server environment. It removes unreferenced private objects older than **24 hours** using the Storage API, including images orphaned by failed commits or account/attempt deletion. Referenced answers remain with their attempts; deleting an account/attempt cascades its records and cleanup removes the bytes after the grace period. The maintenance command continues to work when the student-facing feature flag is off. Monitor nonzero cleanup exit codes.

Upload leases last at most **3 minutes**, bounded by request expiry. Interrupted leases become retryable failures on the next status/discovery check. Images are limited to 5 MB JPEG/PNG/WebP, decoded and re-encoded as JPEG to remove metadata, and accessed through owner-checked authenticated endpoints. Images and private storage URLs are never sent to the AI solver. The new flow works across workers and server restarts.

For rollback, turn `MATHLY_ANSWER_SCANS_ENABLED` off and restart; preserve the new tables and private bucket. The skills API serves the original multiple-choice geometry sample while scanning is disabled, including for guest practice and older frontends. Enabling scanning again restores open-ended presentation and access to saved answers. Keep stored answer records for recovery. No destructive down migration is needed.

Integration tests use bundled disposable PostgreSQL and local private test blobs, without project credentials or Docker:

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python -m pytest tests/test_answer_scans.py tests/test_answer_browser.py
```

See [scan verification](docs/answer-scan-verification.md) for coverage and device checks.
