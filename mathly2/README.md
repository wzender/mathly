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

Settings are read from real environment variables, then `mathly2/.env` (optional), then the repository's `.env` (the one mathly1 uses,
with the same Supabase project; both files are git-ignored). Earlier sources win. `mathly2/.env.example` lists every setting. With the Supabase
values empty, the app uses an in-memory store and a "dev only" sign-in that takes an email address; nothing is saved
after a restart. Put your own address in `ADMIN_EMAILS=` (to give roles) or `DEVELOPER_EMAILS=` (every permission) in the file. No variables are needed on the command line.

Open <http://localhost:7861>. To try every screen alone, put your address in `DEVELOPER_EMAILS=` (every permission): a chip for each role
(תלמיד, מורה, מנהל כיתות, מנהל הרשאות, מפתח) appears in the header. A normal flow: an admin (`ADMIN_EMAILS`, or any account an admin
gave the role) gives someone the **manager** role; the manager makes a class (lessons, a teacher, students); the class's teacher adds more
students; a student signs in and sees the lessons of their classes. Roles belong to an email, so they can be given before a first sign-in.

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
| `DEVELOPER_EMAILS` | Developers' email addresses: every permission and the developer tools. The developer role comes only from here |
| `ADMIN_EMAILS` | The first admins. Admins give roles (student, teacher, manager, admin) to other accounts |
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

## Writing the solved examples

A skill's "?" help shows its explanation and, where the bank has one, a **solved example**: one question solved in steps (what is
done, and why) with its answer. No skill has one yet, and every skill works without it. Examples are added skill by skill with a draft,
a teacher's review, and a merge. Students never call the AI.

```bash
# 1. See which skills of a lesson lack an example and what would be sent. Sends nothing, needs no key.
venv/bin/python -m mathly2.scripts.draft_examples draft --lesson t --dry-run

# 2. Ask Claude for drafts. Spends API money (one request per skill). Writes mathly2/content/drafts/t.json
venv/bin/python -m mathly2.scripts.draft_examples draft --lesson t

# 3. The teacher reads mathly2/content/drafts/t.json, fixes what is wrong, and for each good skill sets
#    "approved": true and "reviewed_by": "<their name>".

# 4. Add the approved drafts to the bank. Anything not approved, or breaking the bank's rules, is left out.
venv/bin/python -m mathly2.scripts.draft_examples merge mathly2/content/drafts/t.json
```

`draft` refuses to overwrite an existing review file (it may hold a teacher's work) unless you pass `--force`.
`--skill ID` (repeatable) and `--limit N` choose which skills to draft. `MATH_MODEL` picks the model.
To see what is still missing across the whole bank: `venv/bin/python -m mathly2.scripts.content_gaps`.

The example's shape (`worked_example`: a question, steps each with `do` and a text `why`, and an answer) is checked by
`mathly2/bank.py` every time the bank loads.
