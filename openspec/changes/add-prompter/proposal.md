# Proposal

## Why

Developers record lessons and need a teleprompter for their texts (PRD DEV-2). mathly1 has one; Mathly2 did not, and the developer screen only said it would come later.

## What Changes

- A "פרומפטר" card on the developer screen, below the activity chart: the account's saved texts, an editor for the title, the text and its outline, and buttons to save, delete, start a new text, show the text or its outline full screen, and ask the AI for an outline.
- The full-screen prompter ported from mathly1 (`static/prompter.js`): scrolling, slides, keys, mouse and presentation remote.
- Routes under `/api/prompter` for developers only: list, create, change, delete, and the AI outline.
- The migration `20261119090000_m2_prompter.sql`: the table `m2_prompter_texts` (server-only), and `prompter` (and `worksheet`, which the old check refused) as kinds of AI usage.
- The prompter moves out of `add-developer-tools`, which keeps the lab and the AI usage page.

## Capabilities

### New Capabilities
- `prompter`: saved texts, the full-screen prompter and the AI outline (PRD DEV-2).

### Modified Capabilities

## Impact

- New migration, new store methods in both stores, `ai.outline`, `mathly2/prompter.py`, `static/prompter.js`, `static/prompter_card.js`, and the permission matrix.
- AI usage records the kind `prompter`; the outline is written from the text only, with no person's or class's name.
