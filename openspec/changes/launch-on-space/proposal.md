# Proposal

## Why

mathly2 must replace mathly1 on its Hugging Face Space without risking mathly1's students: the old database stays untouched and the Space can be switched back at any time (PRD 7.3, Fallback).

## What Changes

- Commit and tag mathly1's current code, including its uncommitted work, so the fallback is exactly what ran before.
- Apply the `m2_` migrations to the shared Supabase project; check that no mathly1 table, policy or bucket changed.
- Deploy the `mathly2` image to the Space with its settings (Supabase, teacher, developer and admin emails, AI key, push keys, picture bucket).
- Rehearse the fallback: switch the Space back to mathly1, confirm a mathly1 student's data, switch forward again.
- Pilot solved examples for one lesson with the drafting tool and a teacher's review.

No behavior of the app changes here; the behavior is in the earlier stages' specs (for the fallback: `app-basics`, "mathly1 stays available").

## Capabilities

### New Capabilities

### Modified Capabilities

## Impact

- The Hugging Face Space, the shared Supabase project, and the repository's tags. Tasks are written when this stage starts.
