# Proposal

## Why

The developers who run the app need their own tools: a teleprompter for the texts they record, a lab for testing tools, and a view of what the AI costs (PRD 4.20).

## What Changes

- The prompter from mathly1: saved texts per account, full-screen scrolling with keyboard and mouse controls, and an AI-written outline on request.
- An empty lab page for testing and development tools.
- An AI usage page: calls and estimated cost by day, class and kind.

## Capabilities

### New Capabilities
- `developer-tools`: the prompter, the lab and the AI usage page (PRD DEV-2 – DEV-4).

### Modified Capabilities

## Impact

- Reads the cost records of `ai-help`. New `m2_` table for prompter texts.
- Ports mathly1's `app/prompter.py` and `static/prompter.js`, including its uncommitted outline work once that is committed in mathly1.
