# Design

## Context

See proposal.md for motivation. `app/math_skills.py` requires sample choices; `static/math.js` rotates them unconditionally and keeps progress and try counts in localStorage. There is no persistent question-attempt model. `app/main.py` stores existing photo sessions in memory for 15 minutes; phone uploads authenticate through a bearer link, invoke the AI solver, and retain no image. That flow cannot provide account-only discovery or durable answer attachments.

The repository contains a responsive web app with a PWA manifest, not a native mobile project. This design treats the signed-in mobile web/PWA as the Mathly phone app. Existing Supabase authentication exposes a stable user ID. The current database script is destructive and must not be reused for this addition.

## Goals / Non-Goals

**Goals:** Durable cross-device association; ownership enforced at every boundary; correct behavior under refresh, retry, concurrency, and lost responses; no AI dependency for capture.

**Non-Goals:** Native iOS/Android clients, background push notifications, OCR, automatic grading, teacher review, multiple-page answers, and changing existing multiple-choice mastery behavior. One photograph is accepted per scan request.

## Decisions

### Explicit question type and stable attempts

Add `sample.type: open-ended`; missing type continues to mean multiple-choice. Validate each variant separately. Open-ended samples have no choices and may retain a diagram. Use skill ID plus sample content version as question identity; persist a prompt snapshot/version on an attempt so later content edits cannot silently change what was answered. Add an original geometry sample exercising this variant.

Create `math_question_attempts` with UUID ID, user ID, question ID/version, snapshot, submission status, and timestamps. Resume the owner's active attempt; an explicit new attempt produces a separate ID. Do not treat upload receipt as a correct answer or update mastery. Keeping only local try counts was rejected because another device cannot reliably associate them.

### Additive Supabase persistence and private storage

Add `math_answer_scans` (ID, immutable owner/attempt references, state, expiry, generation, upload lease, timestamps, safe error code) and `math_answer_attachments` (ID, owner, attempt, unique scan ID, private object key, validated media type/size, timestamps). Use composite ownership constraints or equivalent transactional checks to prevent owner/attempt mismatches. Enforce one active scan per attempt and one committed answer per attempt in this first version. Other attempts can have independent pending scans.

Use a private answer-image bucket with server-generated object paths. Enable RLS on new exposed tables, owner-scoped SELECT policies using `auth.uid()`, and deny direct client writes to scan state and attachments. FastAPI validates user ownership and executes narrowly scoped server-side mutations; privileged credentials stay on the server. No user-editable metadata or email-based ownership checks. Serve image bytes through an authenticated owner-checking endpoint with `Cache-Control: no-store`; avoid public or reusable signed image links. Restrict Storage access to the trusted server path and explicit owner reads only if needed.

This follows current [Supabase private bucket guidance](https://supabase.com/docs/guides/storage/buckets/fundamentals) and [Storage access controls](https://supabase.com/docs/guides/storage/security/access-control). In-memory state was rejected because restarts and multiple workers would lose or disagree about attachments. Reusing the existing bearer-link upload was rejected because possession of its token authorizes another phone.

### Authenticated request API and state machine

Add APIs for creating/resuming attempts; creating a scan under an owned attempt; listing the signed-in student's pending scans; reading and confirming a selected scan; beginning and submitting an upload; renewing an expired scan; and reading the attempt attachment. All routes require real authenticated identity even when the deployment otherwise permits guest practice. Unknown and foreign IDs return the same not-found response; unauthenticated access returns sign-in-required. Disabled storage returns a configuration error, never a local-memory substitute.

Persist states `waiting`, `confirmed`, `uploading`, `received`, `failed`, `expired`, and `superseded`. Map waiting/confirmed to Waiting for phone. Requests expire 15 minutes after creation by server time. Discover pending requests on mobile app entry and foreground resume, with bounded polling while open. Show question text and attempt context in a chooser when several requests exist. Desktop polls the selected attempt every two seconds while visible, backs off on errors, and refreshes immediately on resume. Responses are private and uncached. Polling fits the current stack; Realtime and push add infrastructure without being necessary for foreground discovery.

Confirmation is an authenticated transition. Camera access is invoked only from the subsequent student gesture using the phone's capture picker, requesting permission only as the browser requires. Reuse the existing image orientation, compression, and preview techniques without changing the solver endpoints. Retakes stay local until explicit submission. Permission denial or picker cancellation leaves the request resumable. Use HTTPS in deployment for camera support.

### Observable upload, idempotency, and races

Before transferring bytes, the phone begins an upload with an idempotency key; this persists `uploading` so the computer sees transfer status. A conditional database update grants a bounded upload lease to one submission. Use existing 5 MB JPEG/PNG/WebP limits, validate actual decoded image content and dimensions server-side, and strip metadata through re-encoding. Never trust a client-supplied object path, owner, question, or attempt during upload.

Store the image privately, then atomically insert the attachment and transition the matching scan generation to `received` after rechecking ownership, lease, expiry, and active attempt. A database transaction/function must enforce these conditions across workers; Python check-then-write is insufficient. Where a privileged database function is necessary, keep it unexposed, revoke PUBLIC execution, pin its search path, and restrict execution to the backend role. It is not a public authorization bypass.

Return success only after commit. Lost-response retries query the existing result and return the same attachment; another in-flight submission gets a conflict and refreshes status. A failed commit deletes the staged object when possible; periodic cleanup removes unreferenced objects. An abandoned upload lease becomes failed and retryable while its request is valid. Requests past expiry become expired, including stale uploads; finalization cannot accept them.

Retry of an unexpired failed request uses the same attempt and a new lease. Renewal supersedes the prior request and creates a new 15-minute generation for that attempt. Reject late commits from older generations; serialize renewal and completion on the attempt so only one wins. Never replace a received answer through scan retry. The preview stays available in the phone page after transient failure; no offline image persistence is introduced.

## Risks / Trade-offs

- Storage and database commits are separate → stage objects, finalize transactionally, and clean orphans; report success only after finalization.
- Browser camera behavior varies → preserve capture picker fallback, test denial/cancellation on target devices, and document HTTPS requirements.
- Polling adds requests → pause when hidden and back off; status resumes on foreground entry.
- Guest mode lacks account ownership → keep guest practice available but require sign-in for answer scans.
- New persistent handwritten images change data retention → retain committed images with their attempts, cascade user/attempt deletion through a cleanup process, and purge unreferenced staging images after 24 hours. No images enter the AI solver or diagnostic logs.

## Migration Plan

1. Generate a separate additive migration for the new tables, constraints, indexes, functions, grants, RLS, and private bucket. Do not rerun `docs/mathly-supabase.sql`.
2. Verify ownership policies with two test accounts and unauthenticated callers, including direct table/storage access. Verify conditional finalization and renewal with concurrent requests.
3. Deploy backend and mobile/desktop UI together; expose capture only when authenticated answer storage is configured. Add one open-ended geometry sample after compatible rendering is deployed.
4. Run the API and browser acceptance suite plus existing choice and photo-solver regressions. Document setup, TTLs, cleanup, and retention in README.
5. Roll back by disabling `MATHLY_ANSWER_SCANS_ENABLED`; the skills endpoint then serves the retained original choice sample for compatibility with guest practice and older frontends. Preserve new tables and private objects for recovery. No existing tables or solver sessions need migration. Cleanup remains available with server credentials while student scanning is disabled.
