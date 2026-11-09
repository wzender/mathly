# Tasks

## 1. Fewer and parallel calls

- [x] 1.1 Add the timing test: a store that waits 0.1 seconds on every call, then home, path, a skill, grades and the collection each answer in under 0.55 seconds and an answer in under 0.75; verify it fails on today's code (it is the measurement) and passes after 1.2 and 1.3
- [x] 1.2 Read each fact once per request (a student's classes) and make independent reads at the same time (a small shared thread pool); combine the answer's two progress writes into one and pass the progress along instead of reading it again; verify the existing answer, mastery, rewards, quiz and test tests still pass unchanged
- [x] 1.3 Keep the database connections open: one connection per thread, reused, reconnecting once when the server closed it; verify request tests that several calls reuse one connection, a dropped connection is retried once, and an error from the database is still reported as before

## 2. Wrap-up

- [x] 2.1 Add the PRD line; measure again with the counting script and report the new counts; verify `openspec validate fewer-database-calls --strict` and the mathly2 tests pass
