# Tasks

## 1. Question model and owned attempts

- [x] 1.1 Add open-ended sample typing and version identity in `app/math_skills.py`; extend `tests/test_math_skills.py` to accept open-ended samples without choices and reject malformed variants while retaining existing choice validation.
- [x] 1.2 Generate a separate additive Supabase migration for attempts, scans, attachments, ownership constraints, indexes, RLS, grants, and private storage; verify clean application in a disposable database and confirm existing class data remains intact.
- [x] 1.3 Add a persistence adapter and authenticated create/resume/read attempt endpoints using stable user IDs; verify same-account resume, version changes, forged question IDs, foreign ownership, and guest rejection with API tests.
- [x] 1.4 Document storage/auth setup and the additive migration in README; verify setup steps against the disposable environment without rerunning the destructive legacy script.

## 2. Request lifecycle and durable attachment

- [x] 2.1 Implement create/discover/read/confirm/renew scan APIs with server-clock expiry and generation checks; verify two-account isolation, missing authentication, several pending attempts, expiry, and supersession through API tests.
- [x] 2.2 Implement begin-upload leases, idempotency, image validation/re-encoding, private object storage, and transactional finalization; verify valid image attachment, invalid/oversized data, storage failure, and commit failure without false success.
- [x] 2.3 Enforce serialization of renewal and finalization plus unique attachments across workers; verify concurrent submissions, stale leases, late old-generation commits, and lost-response retries using database integration tests.
- [x] 2.4 Add authenticated image retrieval and staging/deletion cleanup; verify foreign and unauthenticated reads fail through API and direct table/storage access, accepted attachments survive a restart, and orphan images are purged without deleting referenced images.
- [x] 2.5 Document states, 15-minute expiry, lease timeout, errors, cleanup operation, and image retention; verify examples against endpoint responses and ensure no AI key is required for scans.

## 3. Desktop open-ended question flow

- [x] 3.1 Render open-ended questions and diagrams without rotating or displaying choices in `static/math.js`; add a versioned geometry sample and verify browser rendering plus existing multiple-choice feedback and mastery behavior.
- [x] 3.2 Add the localized scan action, attempt restoration, polling, status messages, attachment preview, and failure/expiry retry controls; verify waiting/uploading/received/failed/expired states and question switching in browser tests without attaching an answer to the currently displayed wrong question.
- [x] 3.3 Handle desktop refresh, hidden tabs, reconnect, and sign-out safely; verify polling resumes with server state and no previous-account request or photograph remains visible after account changes.
- [x] 3.4 Document the desktop flow and answer-received versus correctness distinction in README; verify displayed copy and screenshots or browser assertions match the instructions.

## 4. Mobile discovery and camera flow

- [x] 4.1 Add authenticated pending-request discovery on mobile/PWA entry and foreground resume, with question/attempt selection and explicit confirmation; verify same-account discovery, multiple requests, wrong-account isolation, and no camera invocation before confirmation.
- [ ] 4.2 Reuse photo preparation for camera capture, review, retake, and explicit submit with localized accessible controls; verify cancellation, denied permission, rotated images, replacement previews, and no upload before submit in browser tests and a documented phone smoke check.
- [x] 4.3 Connect begin/upload/retry/renew actions, retain the local preview after transient failure, and display durable success; verify upload failures, expired requests, duplicate taps, lost responses, and page resume with two independent browser contexts.
- [ ] 4.4 Document mobile sign-in, confirmation, permission recovery, HTTPS, and retry behavior; verify the documented happy path on the mobile web/PWA and record browser-specific camera limitations.

## 5. Integrated acceptance

- [x] 5.1 Run a complete two-device same-account scan to the original geometry attempt and a second-account rejection case; verify every scenario in both capability specs with API, database, browser, or recorded manual evidence.
- [x] 5.2 Run the existing pytest suite and phone browser regressions alongside new checks; verify existing photographed-problem solving remains independent and functional and that answer upload never awards correctness or mastery.
- [x] 5.3 Rehearse additive deployment and rollback in a disposable environment; verify private answers remain recoverable, rollback hides unsupported open-ended content, and no production data or legacy tables are deleted.
