# Answer scan verification

The automated database tests run the actual additive migration in disposable PostgreSQL. Auth and Storage metadata schemas are minimal local fixtures; private test image bytes are stored on disk. No hosted Supabase project is modified. Storage HTTP requests have separate adapter contract tests; live deployment must still verify the hosted bucket and API configuration.

| Contract | Automated verification |
| --- | --- |
| Open-ended rendering; existing choices | Graph validation and desktop browser checks |
| Stable owned attempt; content changes | API and real database tests |
| Same-account discovery; several requests | Two independent browser contexts and database tests |
| Confirm before camera; review and retake | Mobile browser capture simulation |
| Private requests and images | API, RLS, service-only RPC, and restrictive Storage policies, including a pre-existing permissive policy |
| Waiting/uploading/received/failure/expiry | API state checks and desktop/mobile browser checks |
| Lost response; concurrent finalization | Idempotency and real PostgreSQL concurrent connection tests |
| Expiry, stale lease, renewal | Server-clock database and API tests |
| Restart persistence; deletion cleanup | New application instance against the same database and private files |
| No grading or mastery from upload | Browser progress assertion |
| AI solver remains independent | Existing photo API and phone browser regressions |

## Local verification record — 2026-10-31

- Full suite: `.venv/bin/python -m pytest -q` — **28 passed**, including three new desktop/mobile browser tests and the existing phone-solver browser regression.
- The actual migration was applied through the Supabase CLI to a disposable PostgreSQL database with local Auth/Storage metadata fixtures. The pre-existing class row was preserved. Local `supabase db advisors` returned no issues; migration listing recognized the generated file.
- Verified rollback by disabling scan access: APIs fail closed and the skills endpoint serves the original choice question. Re-enabling restores the open question and access to the same saved image; class and answer records remain intact.
- Browser tests use separate account contexts with an SDK sign-in stub; app APIs, ownership checks, PostgreSQL transactions, and private file reads run normally. They cover several pending requests, confirmation/cancellation, review/retake, upload failure, lost success response, reconnect, expiry/renewal, question switching, reload, and account change. The question version from the displayed graph is sent with attempt creation.
- Image orientation and metadata stripping are checked using actual JPEG EXIF data. Concurrent finalization and renewal run on independent PostgreSQL connections. Storage request methods, paths, headers, and error redaction have adapter contract coverage.
- JavaScript syntax, Python compilation, `git diff --check`, and strict OpenSpec validation pass.
- No hosted migration, live Supabase OAuth/Storage test, or physical iOS/Android camera/PWA test was performed. Tasks 4.2 and 4.4 retain open checkboxes for the real-device checks below, despite their capture UI and documentation being implemented.

## Real-phone smoke check

This is a manual checklist, not a claim that physical devices have been tested. Serve the migrated app over HTTPS with answer scanning enabled, and record device/browser versions and the result.

1. On a computer sign in, open the triangle-area open question, and request a scan.
2. On an actual phone/PWA sign in as the same student. Verify automatic pending-request discovery and correct question/attempt context.
3. Decline confirmation: no camera or permission prompt should appear. Reopen and confirm; then select the camera button.
4. Deny camera permission or cancel capture. Verify guidance and that the request remains available. Enable camera access and retry. Some mobile browsers use an OS capture picker rather than exposing a web camera permission prompt.
5. Photograph a page in portrait and landscape; verify orientation and legibility. Retake and check that only the new preview is submitted.
6. Interrupt network access during upload; restore access and retry. Check that the computer displays one attached answer on the original attempt and that the phone confirms success.
7. Sign out and use a different student account: the old request and image must not appear. Repeat on a second computer tab with a different question to check association.
8. Let a request expire or shorten its expiry in an isolated test project; renew and complete the same attempt.

Physical camera permissions, OS picker behavior, and installed-PWA resume must be checked on supported iOS/Safari and Android/Chrome releases. Browser automation supplies image files and simulates cancellation; it cannot certify those OS interactions.
