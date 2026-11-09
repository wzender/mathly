# Proposal

## Why

mathly2 must replace mathly1 on its Hugging Face Space without risking mathly1's students: the old database stays untouched and the Space can be switched back at any time (PRD 7.3, Fallback).

## What Changes

- Tag mathly1's code exactly as it runs on the Space (`mathly1-final`, the Space's `main` before this change) so the fallback is exactly what ran before.
- Put mathly2 on the same Space: the `mathly2` branch (with mathly1's latest commits merged in, so the push only adds) becomes the Space's `main`, and the repository's root `Dockerfile` builds mathly2. mathly1's code stays in the repository, and its old Dockerfile is kept as `Dockerfile.mathly1`.
- Apply the `m2_` migrations to the shared Supabase project; check that no mathly1 table, policy or bucket changed.
- Deploy the `mathly2` image to the Space with its settings (Supabase, teacher, developer and admin emails, AI key, push keys, picture bucket).
- Rehearse the fallback: switch the Space back to mathly1, confirm a mathly1 student's data, switch forward again.
- Pilot solved examples for one lesson with the drafting tool and a teacher's review.

No behavior of the app changes here; the behavior is in the earlier stages' specs (for the fallback: `app-basics`, "mathly1 stays available").

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- The Hugging Face Space, the shared Supabase project, and the repository's tags. The Space's own settings (secrets) are set by its owner.
