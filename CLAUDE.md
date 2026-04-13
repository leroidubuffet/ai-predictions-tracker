# AI Predictions Tracker — CLAUDE.md

## Project overview

A Bluesky bot and static archive that tracks AI-related predictions made by industry figures, researchers, and companies. The goal is accountability through a permanent, browsable record.

The value is in the **reminders**: a prediction logged today becomes interesting when its deadline approaches. Architecture decisions should reflect this priority.

## Repository structure

```
predictions/          # One YAML file per prediction
  YYYY-MM-DD-slug.yaml
categories.yaml       # Controlled vocabulary for categories
template.yaml         # Copy this when adding a new prediction
new_prediction.sh     # Data entry helper script
state/                # Bot state (reminded_at tracking, etc.)
.github/
  workflows/
    post_new.yml      # Trigger: fires on push to predictions/
    reminders.yml     # Trigger: daily cron scan for upcoming deadlines
site/                 # Static site generator and output
scripts/              # Bot scripts (post.py, reminders.py, validate.py)
```

## Prediction schema

Each prediction is a YAML file in `predictions/`. Filename format: `YYYY-MM-DD-source-slug.yaml`.

```yaml
prediction_date: 2024-03-15
source_name: Sam Altman
source_url: https://...
prediction_text: |
  The full verbatim or closely paraphrased prediction text.
  Multi-line is fine.
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
./new_prediction.sh
```

This opens a pre-filled template in `$EDITOR` with today's date set. Save and exit to commit. For bulk imports or historical seed data, set `skip_post: true` to prevent the bot from posting them.

## Bot architecture

Two separate scripts with different triggers:

**`scripts/post_new.py`** — runs on push to `predictions/`
- Diffs HEAD vs HEAD~1 to find new YAML files
- Skips any with `skip_post: true`
- Posts to Bluesky with source attribution and link
- Formats post: prediction summary + source + deadline if present

**`scripts/reminders.py`** — runs on daily cron (GitHub Actions)
- Scans all `predictions/` files
- Posts reminders at 30 days, 7 days, and 1 day before `deadline`
- Tracks reminder state in `state/reminded.yaml` to avoid duplicate posts
- Only fires for `status: pending` predictions

## Validation

`scripts/validate.py` runs in CI on every push:
- All required fields present
- `category` is in `categories.yaml`
- `status` is one of the allowed values
- `deadline` is a valid ISO date if present
- Filename matches `YYYY-MM-DD-*.yaml` format

## Status field

- `pending` — deadline hasn't passed, no update
- `expired` — deadline passed, no notable update recorded
- `notable` — something worth noting happened; add context in `notes`

This project does not judge prediction accuracy. `notable` means something happened worth recording, not that the prediction was right or wrong.

## Secrets required

- `BLUESKY_HANDLE` — bot account handle
- `BLUESKY_APP_PASSWORD` — Bluesky app password (not main password)

Set these in GitHub repository secrets.

## What to avoid

- Do not install python packages globally (use venv)
- Do not add a backend database
- Do not add user contribution features
- Do not add automated prediction scraping
- Do not post seed/historical data to Bluesky (use `skip_post: true`)
- Do not invent new category slugs without updating `categories.yaml`
- Keep the data entry workflow as fast as possible — friction kills the habit
