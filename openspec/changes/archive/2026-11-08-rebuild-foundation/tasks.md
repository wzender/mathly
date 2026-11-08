# Tasks

## 1. Roles and permissions

- [x] 1.1 Add `DEVELOPER_EMAILS` and `ADMIN_EMAILS` to `config.py`, `.env.example` and the README; verify config tests read them from the environment and from `mathly2/.env`
- [x] 1.2 Add `access.py` with the permission matrix and `need(permission)` (design decision 2); verify unit tests for each role's permissions, and that a developer has every permission
- [x] 1.3 Resolve roles per request from the settings, `m2_roles` and class teachers, with a 30-second cache (decision 1); verify tests for a settings developer, a class teacher not in any setting, a role given in the table, several roles at once, and a plain student

## 2. Storage

- [x] 2.1 Add the migration for `m2_roles`, the new `m2_classes` columns and check, the case-insensitive unique name, and the (class_id, email) key (decision 3); verify a pgserver test applies all migrations, a student can join two classes, a teacher listed as a student is refused, and browser roles are refused
- [x] 2.2 Add role and class methods to `InMemoryStore` (roles by email, give, take with the last-admin guard, classes with lessons and AI fields, students in several classes, known accounts); verify unit tests for each
- [x] 2.3 Add the same methods to `SupabaseStore`; verify request tests with the faked PostgREST, including the one-step last-admin guard

## 3. API

- [x] 3.1 Extend `GET /api/me` with roles, permissions and classes as student and as teacher; verify tests for each role and for a person with several roles
- [x] 3.2 Move class creation, editing and deletion to the manager (`/api/classes`), with lessons, teacher, AI switch and budget; verify tests that a manager can and a teacher cannot, that names are unique ignoring case, and that deleting keeps progress
- [x] 3.3 Add the roster routes for a class's teacher or a manager (`/api/classes/{id}/students`); verify tests for pasting, invalid addresses, a student in two classes, removing, and a teacher of another class refused
- [x] 3.4 Add `GET /api/teaching` and `GET /api/students`; verify tests for a teacher of two classes and the manager's list showing a student's two classes
- [x] 3.5 Add the admin routes (`/api/accounts`, give and take a role); verify tests for a role given before first sign-in, the developer role refused, and the last admin unable to remove themselves
- [x] 3.6 Add a test that reads every route and checks each refuses the roles outside its permission (spec: Permissions per role); verify it passes and the "no content before sign-in" test still passes

## 4. Screens

- [x] 4.1 Replace the color tokens in `app.css` with the `--sky-*` tokens (one dark set), the owl SVG and one reduced-motion rule, and the sky background of two glows and small stars (decision 6); verify a Playwright test that the background is dark even when the device asks for light mode and that nothing animates under reduced motion
- [x] 4.2 Rebuild the sign-in page as mathly1's (logo, owl, status line, one Google button; the dev sign-in when Supabase is not set), with the "could not connect, try again" state; verify Playwright tests for the page and for the failure state
- [x] 4.3 Add the role switcher in the header for people with several roles, remembering the last choice; verify a Playwright test with a manager who is also a teacher
- [x] 4.4 Build the manager's screens: class list, class editor (name, lessons, teacher, students, AI switch, budget) and students list; verify Playwright tests at 390px and 1280px that create, edit and delete a class with no sideways scrolling
- [x] 4.5 Build the teacher's home: classes taught, each with its students, adding and removing students; verify a Playwright test that a teacher adds 3 emails and removes one, and cannot reach the class editor
- [x] 4.6 Build the admin's accounts screen and every account's own-access page; verify Playwright tests for giving the manager role to a new email and for the last-admin message

## 5. Exercise bank

- [x] 5.1 Update `scripts/content_gaps.py` to list skills without a solved example, skills without or with few questions, and mistakes without a skill to go back to; verify its tests on the real bank (96 without a solved example, 1 without questions, 204 mistakes without one)

## 6. Integration

- [x] 6.1 Walk the roles end to end in a browser test: an admin gives the manager role, the manager creates a class with a teacher and two students, the teacher adds a third, a student signs in and sees their lessons; verify the test passes
- [x] 6.2 Run `venv/bin/python -m pytest mathly2/tests` and `openspec validate rebuild-foundation --strict`; verify both pass

## 7. Found while using it (decisions 7 to 10)

- [x] 7.1 Read the repository's `.env` after the app's own (`config.py`), keeping the environment first; verify config tests for the order and for a test file being read alone, and that the whole suite stays independent of real keys
- [x] 7.2 Keep what was typed when a class save is refused and show the reason above the save buttons, scrolled into view; verify a Playwright test that a student named as teacher is refused in view, keeps the typed values, and saves after the fix
- [x] 7.3 Report database refusals that are not conflicts as a 503 with a clear message and a log line, and read the database's error body once; verify store tests for refusals other than 409 and an API test for the 503
- [x] 7.4 Keep the address on the first screen after sign-in and clear it only when the role is switched; verify a Playwright test that a link and a reload land on the collection and a role switch clears the address

## Workflow follow-up

- Archive this change once it is reviewed, so `accounts-and-classes`, `app-basics` and `exercise-bank` carry the new requirements; then propose `add-learning-core` in full (design and tasks).
