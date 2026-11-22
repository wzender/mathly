# Proposal

## Why

The developer wants to know every morning how much was practised the day before, without opening the app.

## What Changes

- `GET /api/dev/report` gives one day (yesterday by default) in counts only: practice answers and right ones, the people who practised, rounds and tests by kind, each class's share, and the week.
- It is read by the developer, or with a report key (`REPORT_TOKEN` in the Space's settings) so that a scheduled task, which cannot sign in, can read it and send a summary each morning.

## Capabilities

### New Capabilities

### Modified Capabilities
- `system-status`: the morning report.

## Impact

- `report.py` (new), `config.py` (`REPORT_TOKEN`), `store.py` (`correct_on`, `attempts_started_on`), `main.py`. PRD DEV-7.
