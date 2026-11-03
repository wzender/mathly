# Proposal

## Why

Students need to submit handwritten reasoning and drawings for open-ended questions. Mathly currently offers multiple-choice practice and phone-based AI problem solving, but cannot securely attach a student's photographed answer to the correct question attempt.

## What Changes

- Support open-ended question samples without predefined answer options.
- Add persistent, student-owned question attempts and answer attachments.
- Let a student request a phone scan from an open question and discover pending requests in the mobile app after signing in to the same account.
- Require confirmation before camera access, offer preview and retake, and confirm successful submission on both devices.
- Show waiting, uploading, received, failure, and expiry states; allow safe retries without duplicate attachments or association with a different attempt.
- Keep the existing photographed-problem solver available as a separate flow.

## Capabilities

### New Capabilities

- `open-question-answers`: Open-ended question rendering, owned attempts, and persistent photographed answer attachments.
- `phone-answer-scans`: Same-account request discovery, confirmation, capture, submission, status synchronization, expiry, and retries.

### Modified Capabilities

None. This repository has no main capability specifications yet.

## Impact

- Question validation in `app/math_skills.py`, sample content, and question rendering in `static/math.js`.
- Authenticated attempt and scan APIs in `app/main.py` with a dedicated persistence module.
- Existing account integration in `app/auth.py`, mobile/PWA entry in `static/index.html`, and reusable photo preparation from `static/photo-image.js`.
- Additive Supabase tables and private image storage; use a separate migration rather than rerunning the destructive `docs/mathly-supabase.sql` script.
- API, ownership, concurrency, and desktop/mobile browser coverage alongside current phone-solver tests.
