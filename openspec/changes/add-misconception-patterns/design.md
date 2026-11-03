# Design

## Context

Progress lives in one object `P` in localStorage (`mathly.progress.v1:<email>`), saved by `save()` in `static/math.js`. The scoring rules live in `static/math-sky.js` (`window.MathlySky`), whose `ensure(P)` fills missing fields so older saved progress keeps loading. Wrong answers reach three places, each of which already knows the choice's mistake tag (`data-m` on the button, or `choice.mistake`):

- `answer()`: skill practice. Calls `Sky.wrong(P,id)` and shows `G.mistakes[m]`.
- `reviewAnswer()`: mixed review. Calls `Sky.reviewed` and `Sky.wrong`.
- `quizSubmit()`: practice exam. Already builds a per-exam mistake tally, but doesn't keep it.

`G.mistakes[tag]` has `name`, `tip` and `back` (a skill id or `null`). The home screen is assembled in the path view as `topBar() + daily() + reviewCard() + examSoon() + quizCard() + …`.

## Goals / Non-Goals

**Goals:**
- One place that writes a log entry, called from the three answer paths.
- Pure summary logic in `math-sky.js`, testable through the page without UI.
- The data shape is ready for a later personal path to read.

**Non-Goals:**
- Syncing the log to the server or a teacher view.
- Changing what any activity shows or scores today.
- Open-ended or photographed answers (they have no tags).

## Decisions

**Log shape: an array `P.slips` of `{at, id, q, m, via}`.** `at` is an ISO time, `id` the skill, `q` the question index, `m` the tag, and `via` is `"practice" | "review" | "exam"`. The newest are kept last and the array is capped at 500. A flat append-only log is chosen over pre-aggregated counters per tag because the 30/14/60-day windows and the later personal path need the time of each event. 500 short entries are about 40 KB, well inside localStorage. `ensure()` creates `slips` as an array, as it already does for `comets`.

**`Sky.slip(P, id, q, m, via, now)` writes; `Sky.patterns(P, mistakes, now)` reads.** `patterns` returns `{recurring:[…], stopped:[…]}`. Each item is `{m, n, skills:[ids by count], last, practise}`. `practise` is `mistakes[m].back`, or else the skill where `m` came up most, with ties going to the most recent. Ranking: number of distinct skills, then count, then most recent. Both lists are cut to 3. For "stopped", a sliding pass over the tag's sorted times checks whether any two entries are 30 days or less apart. Keeping this in `math-sky.js` next to `due`/`streak` follows the existing split: rules there, screens in `math.js`.

**Practice exam logs on hand-in, in `quizSubmit`**, from the final `res` list, not when picks are made, because picks can change and a left exam is discarded. All entries share the hand-in time.

**Questions are logged by index (`q`).** This matches `P.solved`/`P.missed`. If question lists change, an old index may point at a different question. The summary only uses `m` and `id`, so that doesn't matter.

**UI: `patternsCard()` after `reviewCard()` on the home screen, and a `showPatterns()` sheet opened by `data-act="patterns"`.** These reuse the existing sheet markup (`mx-sheet`, `mx-shtop`, `mx-x`) and buttons with `data-id` that already open a skill's practice. Copy, in Hebrew and plural like the rest of the app:
- Card title: "דפוסים שחוזרים". Body: "‎<name> הופיעה ב־N מיומנויות לאחרונה. כדאי לחזק." With only stopped patterns: "‎<name> כבר לא חוזרת. כל הכבוד על התיקון."
- Each sheet entry: name, tip, "N פעמים ב־K מיומנויות · לאחרונה <relative day>", and a "לחזק: <short>" button.
- The stopped section is headed "דפוסים שנעלמו".

The card sits after review so that today's due review stays first: retrieval comes before targeted work.

## Risks / Trade-offs

- [A guess or a slip is counted as a misconception] → It needs two occurrences within 30 days before it shows, and only the top three are shown.
- [Showing mistakes may discourage some students] → The words are about the mistake, the card links straight to an action, and patterns that stopped are shown as a win.
- [The log exists on one device only] → Accepted for now, as with all progress; moving it to the server is a later change.
- [Tag names reused across topics with different meanings] → Tags are global in `math_algebra9.json` by design. Only the skill list reveals the spread.

## Migration Plan

No migration is needed. `ensure()` adds an empty `slips` to old progress. Rolling back leaves an unused `slips` array in storage, which is harmless.
