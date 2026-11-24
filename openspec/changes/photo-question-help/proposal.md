# Proposal

## Why

A student who does not know how to start asks the AI for the answer before trying, and an unclear check or answer has no follow-up.

## What Changes

- "💬 עזרה" on a photographed question: a conversation with an AI tutor and a ladder of hints (a direction, the next step, the full solution), each lowering the grade the question can still reach; a free question costs nothing.
- Before the full solution the tutor guides without giving the answer; after the check it explains the grade, the board and the solution.
- Limits per question and per day; the teacher sees the conversation.
- With the Gemini key set, the photographed question replaces the old photo help on home and on the exercise screen.

## Capabilities

### New Capabilities

### Modified Capabilities
- `ai-help`: help on a photographed question.

## Impact

- `photoq.py` (the help route, the grade cap), `boardreview.py` (`tutor_reply`), `store.py`; `static/photoq.js`, `static/teacher_photoq.js`, `static/home.js`, `static/exercise.js`. Migration `20261126090000_m2_photo_help.sql`. PRD.
