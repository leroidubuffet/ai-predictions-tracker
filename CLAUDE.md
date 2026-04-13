# AI Predictions Tracker — CLAUDE.md

## Project overview

A Bluesky bot that posts AI industry predictions and deadline reminders. Predictions are stored as YAML files in a git repository. Two GitHub Actions workflows handle posting: one fires on push (new predictions), one runs daily (deadline reminders).

The value is in the **reminders**: a prediction logged today becomes interesting when its deadline approaches.

## Repository structure

```
predictions/          # One YAML file per prediction
  YYYY-MM-DD-slug.yaml
categories.yaml       # Controlled vocabulary for categories
template.yaml         # Copy this when adding a new prediction
new_prediction.sh     # Data entry helper script
state/
  reminded.yaml       # Bot state — tracks which reminders have been sent
.github/
  workflows/
    validate.yml      # Runs on push: validates all prediction files
    post_new.yml      # Runs on push to predictions/: posts new entries to Bluesky
    reminders.yml     # Runs daily: scans for upcoming deadlines and posts reminders
scripts/
  validate.py         # Schema validation
  validate_test.py    # Validation tests
  post_new.py         # New prediction Bluesky poster
  post_new_test.py    # Post formatting tests
  reminders.py        # Deadline reminder scanner and poster
  reminders_test.py   # Reminder logic tests
requirements.txt
```

## Prediction schema

Each prediction is a YAML file in `predictions/`. Filename format: `YYYY-MM-DD-source-slug.yaml`.

```yaml
prediction_date: 2024-03-15
source_name: Sam Altman
source_url: https://...
prediction_text: |
  The full verbatim or closely paraphrased prediction text.
deadline: 2027-12-31        # ISO date, optional
deadline_fuzzy: "end of 2027"  # Human-readable, optional
category: agi               # Must match an entry in categories.yaml
status: pending             # pending | expired | notable
notes: |
  Optional context, clarifications, or outcome notes.
skip_post: false            # Set true for seed/historical data
```

## Valid categories

Defined in `categories.yaml`. Always lowercase hyphenated slugs. Do not invent new categories without adding them to that file first.

Current vocabulary: `agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`

## Adding a prediction

```bash
./new_prediction.sh "Source Name"
```

This opens a pre-filled template in `$EDITOR` with today's date set, validates on save, and commits on success. For bulk imports or historical seed data, set `skip_post: true` to prevent the bot from posting them.

## Bot architecture

Two separate scripts with different triggers:

**`scripts/post_new.py`** — runs on push to `predictions/`
- Diffs HEAD vs HEAD~1 to find new YAML files only (not edits)
- Skips any with `skip_post: true`
- Posts to Bluesky: source, prediction excerpt (truncated to fit 300 chars), deadline if present

**`scripts/reminders.py`** — runs on daily cron
- Scans all `predictions/` files
- Posts reminders at 30, 7, and 1 days before `deadline`
- Tracks reminder state in `state/reminded.yaml` to avoid duplicates
- Only fires for `status: pending` predictions without `skip_post: true`

## Validation

`scripts/validate.py` runs in CI on every push:
- All required fields present and non-empty
- `category` is in `categories.yaml`
- `status` is one of the allowed values
- `deadline` is a valid ISO date if present
- `prediction_date` is a valid ISO date
- `skip_post` is a boolean
- Filename matches `YYYY-MM-DD-*.yaml` format

## Status field

- `pending` — deadline hasn't passed, no update
- `expired` — deadline passed, no notable update recorded
- `notable` — something worth noting happened; add context in `notes`

This project does not judge prediction accuracy.

## Python environment

Always use the `.venv` virtual environment. Never install packages globally.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Secrets required

- `BLUESKY_HANDLE` — bot account handle
- `BLUESKY_APP_PASSWORD` — Bluesky app password (not main password)

Set these in GitHub repository secrets.

## What to avoid

- Do not build any website or static site — this is a bot-only project
- Do not add a backend database
- Do not add user contribution features
- Do not add automated prediction scraping
- Do not post seed/historical data to Bluesky (use `skip_post: true`)
- Do not invent new category slugs without updating `categories.yaml`
- Do not install Python packages globally (use `.venv`)
- Keep data entry fast — friction kills the habit
