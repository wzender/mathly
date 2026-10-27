---
title: Mathly
emoji: 🧮
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Mathly

Mathly is a Hebrew ninth-grade algebra and geometry practice path. It contains 59 skills across seven units, immediate feedback for known mistakes, and optional photographed-problem help.

Choose **צילום בטלפון, פתרון במחשב** on the computer, scan the QR code with your phone, take a photo, and confirm sending it. The answer and worked solution appear automatically on the computer. Links last 15 minutes and accept one exercise; the phone does not need a separate login. Geometry practice includes diagrams for rectangle area, triangle area, and Pythagoras.

Both devices must be able to reach the same app URL. For local use, open the computer's LAN address (for example `http://192.168.1.10:7860`) on both devices instead of `localhost`. Phone links and results are temporary in server memory: use a single server worker; restarting it clears active links. Images are sent to the configured AI provider for solving and are not stored by Mathly.

## Run locally

```bash
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 7860
```

Open <http://localhost:7860>. Authentication is disabled when the Supabase values are empty.

## Configuration

Copy `.env.example` to `.env`. `ANTHROPIC_API_KEY` enables photographed-problem help. Supabase settings enable Google sign-in and math-class rosters.

For an existing deployment, back up Supabase and then run [docs/mathly-supabase.sql](docs/mathly-supabase.sql) in its SQL editor. The migration deliberately deletes the removed product's tables and non-math classes.

## Tests

```bash
venv/bin/python -m pytest
```
