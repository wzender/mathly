# Tasks

- [x] 1.1 Classify the bank's questions that need no board into `content/onthego.json`. Verify with `test_onthego_api.py` (every key in the bank, most lessons have some).
- [x] 1.2 Add `onthego.py`, the start route and the round's view (`rounds.py`), and the count on home. Verify with the API tests and the permission matrix.
- [x] 1.3 Add the migration for the kinds `onthego_round` and `mistakes_round`. Verify with `test_migrations.py` on a local PostgreSQL.
- [x] 1.4 The home button, the route and the round without a board (`home.js`, `student.js`, `round.js`). Verify with the browser test.
- [x] 1.5 Update the PRD (STU-1). Verify that `openspec validate practice-on-the-go --strict` passes.
