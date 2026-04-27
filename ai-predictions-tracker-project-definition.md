# AI Predictions Tracker — Project Definition

## Overview

A Bluesky bot that tracks AI-related predictions made by industry figures, researchers, and companies. It maintains a permanent record of claims and forecasts in a git repository, and posts to Bluesky both when new predictions are added and when their deadlines approach.

## Purpose

Create an accountability layer for AI discourse by recording:
- What was claimed, and when
- Who made the claim
- What timeframe was specified (when applicable)
- What actually happened (when notable)

The core vaule is **accountability**. The bot reminds what was predicted, helping the public remember about it and make claimers accountable for their predictions.

## Scope

Solo-maintained project. Sustainability requires that data entry stays fast and infrastructure stays minimal. If it's not easy to add a prediction in under two minutes, the project dies.

## Target Audience

Bluesky followers interested in AI industry accountability and the gap between what was claimed and what happens and what happened.

---

## Technical Design

### Storage: One YAML file per prediction

Each prediction lives in `predictions/YYYY-MM-DD-source-slug.yaml`.

**Why not CSV:** Free-text fields with commas, quotes, and newlines break CSV editing and produce unreadable git diffs. YAML handles multi-line text naturally and diffs cleanly.

#### Schema

```yaml
prediction_date: 2024-03-15
source_name: Sam Altman
source_url: https://...
prediction_text: |
  The full verbatim or closely paraphrased prediction.
deadline: 2027-12-31        # ISO date, optional
deadline_fuzzy: "end of 2027"  # Human-readable form, optional
category: agi               # Must be in categories.yaml
status: pending             # pending | expired | notable
notes: |
  Optional context, source details, or outcome notes.
skip_post: false            # true for historical/seed data
```

#### Status values

- `pending` — deadline hasn't passed
- `expired` — deadline passed, nothing notable recorded
- `notable` — something worth noting happened (record in `notes`)

### Categories

Defined in `categories.yaml` as a controlled vocabulary. Lowercase hyphenated slugs only. Validated in CI.

Initial set: `agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`

### Data Entry

A `new_prediction.sh` script opens a pre-filled YAML template in `$EDITOR` with today's date already populated, runs validation, and commits on success.

---

## Bot Architecture

Two separate bots with different triggers.

### Bot 1: New prediction poster

- **Trigger:** GitHub Actions on push to `predictions/`
- **Logic:** Diff HEAD vs HEAD~1, find new YAML files, skip `skip_post: true`
- **Posts:** Prediction summary, source attribution, deadline if present

### Bot 2: Deadline reminder

- **Trigger:** GitHub Actions daily cron
- **Logic:** Scan all predictions, find `status: pending` with `deadline` within 30/7/1 days
- **State:** Tracks which reminders have been sent in `state/reminded.yaml`
- **Posts:** "X said Y would happen by Z — that's N days away"

The reminder bot is the higher-value feature. A new prediction is a data point. A reminder near a deadline is accountability.

### Seed data handling

Historical predictions are added with `skip_post: true`. The new-prediction bot ignores them. The reminder bot will still fire for them as deadlines approach.

---

## Infrastructure

- **Storage:** GitHub repository (YAML files)
- **CI/Validation:** GitHub Actions — validates schema and categories on every push
- **New post trigger:** GitHub Actions on push to `predictions/`
- **Reminder trigger:** GitHub Actions daily cron
- **Secrets:** `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` in GitHub repository secrets

No backend. No server. No website. GitHub Actions is the compute layer.

---

## Phases

1. Data foundation — schema, template, seed predictions
2. Validation — CI checks on every push
3. Data entry script — `new_prediction.sh`
4. New prediction bot — posts on push
5. Reminder bot — daily deadline scan
6. Hardening — rate limits, state drift, end-to-end tests

---

## Out of Scope

- Any website or static site
- User contributions or comments
- Backend database
- Automated prediction scraping
- Mobile app
- Judging prediction accuracy
