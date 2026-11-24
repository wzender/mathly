## Why

The AI chat was only on the skill's sheet from the path; the questions students practise most come from home's lesson rounds, which had no chat.

## What Changes

- 💬 in the rounds' sheet too: a lesson round, a mistakes round and a round on the go (`POST /api/rounds/{round_id}/tutor`).
- The round's next question is "on screen" (guide); a question the round has answered is "answered" (explain); a later one is refused.
- A round's answer after asking about that question the same day does not count for mastery.
- The chat's screen code is shared (`static/tutor_chat.js`) by the skill's sheet and the rounds.

## Impact

`mathly2/practice_tutor.py`, `mathly2/rounds.py`, `mathly2/store.py` (`tutor_chat`), `mathly2/static/tutor_chat.js`, `mathly2/static/round.js`, `mathly2/static/exercise.js`. No new migration.
