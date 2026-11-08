# Tasks

## 1. The round on the server

- [x] 1.1 Add the migration `20261111100000_m2_rounds.sql` (`round_start` on `m2_skill_progress`), `mistake_id` and the round in `answers_of`, in both stores; verify unit and migration tests (the column defaults to nothing, nothing else changes, the browser roles are still refused)
- [x] 1.2 Replace the next-question rule by the round: the answers since `round_start`, the next question is an unanswered one at random, none when all are answered; remove the "missed returns" rule; verify unit tests: each question once, never twice in a round, a one-question skill, the 10 questions of a 30-question skill, an old student without a round start begins a new round
- [x] 1.3 Reshape `GET /api/skills/{id}` and the answer to carry the round (answered, total, a result per answer, done, and when done the result with the mistakes) and add `POST /api/skills/{id}/round`; verify API tests: ten answers end the round with no next question and a result, a wrong question never returns, leaving and coming back continues or shows the result, a new round starts all ten again in a new order, mastery counts across rounds, and the waits test still passes

## 2. The screen

- [x] 2.1 Show the counter and dots by the round (filled, marked wrong, empty), the wrong-answer feedback with "לשאלה הבאה", and no countdown after the last question; verify a Playwright test
- [x] 2.2 Add the round's result view with "סבב חדש" and the way back; verify a Playwright test: ten answers with three wrong show "7 מתוך 10", the mistakes with names and tips and no right answers, a reload shows the result again, "סבב חדש" starts again with ten dots

## 3. Wrap-up

- [x] 3.1 Update the PRD, the older tests that assumed repeated questions, and run the whole suite and `openspec validate ten-question-rounds --strict`; verify they pass
