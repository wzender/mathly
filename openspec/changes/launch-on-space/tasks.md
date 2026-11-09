# Tasks

## 1. Keep the way back

- [x] 1.1 Tag the Space's current code as `mathly1-final` and push the tag; verify `git rev-parse mathly1-final^{commit}` equals what the Space's `main` was
- [x] 1.2 Keep mathly1's Dockerfile as `Dockerfile.mathly1`; verify that building it from the tag's tree still works, by reading that its COPY lines name only `app` and `static`

## 2. Build mathly2 on the Space

- [x] 2.1 Merge the Space's latest `main` (mathly1) into the `mathly2` branch so the push only adds; verify `git merge-base --is-ancestor origin/main HEAD`
- [x] 2.2 Make the root `Dockerfile` build mathly2 (the content of `mathly2/Dockerfile`) and describe mathly2 in the README's text below the Space's front matter, which stays as it is; verify `docker build` of the root Dockerfile succeeds and the container answers `/api/me` with 401 and `/` with the app page
- [x] 2.3 Verify the container with the Supabase settings from `.env` starts, serves `/`, and refuses a half-configured start; verify no migration or table of mathly1 is touched by reading the migrations for statements on tables without the `m2_` prefix

## 3. Switch

- [ ] 3.1 Run the full suite; push the `mathly2` branch to the Space's `main` (a push that only adds); verify the Space builds and `/` answers
- [x] 3.2 Tell the Space's owner which secrets mathly2 reads (`SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SECRET_KEY`, `TEACHER_EMAILS`, `DEVELOPER_EMAILS`, `ADMIN_EMAILS`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT`); verify the list against `config.py`

## 4. The fallback

- [x] 4.1 Document how to switch back (`git push origin mathly1-final^{commit}:main --force`, noting what it does) in the README; the rehearsal on the live Space is done by the owner after the switch
