# Mathly 2

The rebuilt Mathly app. Requirements: `docs/tasks/prd-mathly.md`; specs and plans: `openspec/`.
The current app (`app/`, `static/`) is separate and keeps running until this one replaces it.

## Run locally

Run these from the repository root.

```bash
python3 -m venv venv
venv/bin/python -m pip install -r mathly2/requirements-dev.txt
venv/bin/python -m uvicorn mathly2.main:app --port 7861
```

Open <http://localhost:7861>. With the Supabase settings empty, the app uses an in-memory store and a
"dev only" sign-in that takes an email address; nothing is saved after a restart.
Add teachers with `TEACHER_EMAILS=you@school.example venv/bin/python -m uvicorn …`.

## Tests

```bash
venv/bin/python -m playwright install chromium   # once, for the browser tests
venv/bin/python -m pytest mathly2/tests
```

## Settings

| Setting | Meaning |
|---|---|
| `SUPABASE_URL` | The Supabase project's URL |
| `SUPABASE_PUBLISHABLE_KEY` | The publishable key. Sent to the browser for Google sign-in |
| `SUPABASE_SECRET_KEY` | The secret key. Server only; never sent to the browser |
| `TEACHER_EMAILS` | Teachers' email addresses, separated by commas, spaces or new lines |
| `PORT` | The port in the container (default 7860) |

Set all three Supabase values or none. With none, the app runs locally with the in-memory store and the
"dev only" sign-in; with only some, the server refuses to start (so a half-configured deployment can never
accept any email address as a sign-in).

## Database

Run the files in `mathly2/supabase/migrations/` in order (the Supabase SQL editor or `supabase db push`).
They add only tables named `m2_…`, which only the server can read or write; the current app's tables are untouched.
Turn on Google sign-in in the Supabase project and add the app's address to its redirect URLs.

## Docker

Build from the repository root:

```bash
docker build -f mathly2/Dockerfile -t mathly2 .
docker run --rm -p 7860:7860 mathly2        # then open http://localhost:7860
```

Add `-e SUPABASE_URL=… -e SUPABASE_PUBLISHABLE_KEY=… -e SUPABASE_SECRET_KEY=… -e TEACHER_EMAILS=…` for a real run.
A Hugging Face Space needs the Dockerfile at the top of its repository: create the Space from a copy of this repository
whose root `Dockerfile` is `mathly2/Dockerfile` with the `mathly2/` paths unchanged, and set the settings above as Space secrets.

## Content the bank still lacks

```bash
venv/bin/python -m mathly2.scripts.content_gaps
```
