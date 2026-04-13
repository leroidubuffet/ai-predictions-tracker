# AI Predictions Tracker — Project Definition

## Overview

A Bluesky bot and static archive that tracks AI-related predictions made by industry figures, researchers, and companies. The bot creates a permanent, browsable public record of claims and forecasts as they're made.

## Purpose

Create an accountability layer for AI discourse by recording:
- What was claimed, and when
- Who made the claim
- What timeframe was specified
- What actually happened (when notable)

The core value is **reminders near deadlines**, not initial posts. A prediction logged in 2024 matters most in 2026 when the deadline arrives. The architecture prioritizes this.

## Scope

Solo-maintained project. Sustainability requires that data entry stays fast and infrastructure stays minimal. If it's not easy to add a prediction in under two minutes, the project dies.

## Target Audience

Readers interested in AI industry accountability, historical record of predictions, and understanding the gap between what was claimed and what happened.

---

## Technical Design

### Storage: One YAML file per prediction

Each prediction lives in `predictions/YYYY-MM-DD-source-slug.yaml`.

**Why not CSV:** Free-text fields with commas, quotes, and newlines break CSV editing in GitHub's web UI and produce unreadable diffs. YAML handles multi-line text naturally, diffs cleanly in git, and doesn't require a parser to read manually.

#### Schema

```yaml
prediction_date: 2024-03-15
source_name: Sam Altman
source_url: https://...
prediction_text: |
  The full verbatim or closely paraphrased prediction.
  Multi-line text works naturally here.
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

The project does not judge accuracy. `notable` means "worth recording," not "right" or "wrong."

### Categories

Defined in `categories.yaml` as a controlled vocabulary. Lowercase hyphenated slugs only. Validated in CI. Do not add predictions with invented categories.

Initial set: `agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`

### Data Entry

A `new_prediction.sh` script opens a pre-filled YAML template in `$EDITOR` with today's date already populated. The entire workflow:

```bash
./new_prediction.sh   # edit, save, done
```

This is intentionally faster than GitHub's web UI. For bulk historical imports, edit files directly and set `skip_post: true`.

---

## Bot Architecture

Two separate bots with different triggers. These are different problems — conflating them causes both to be designed poorly.

### Bot 1: New prediction poster

- **Trigger:** GitHub Actions on push to `predictions/`
- **Logic:** Diff HEAD vs HEAD~1, find new YAML files, skip `skip_post: true`
- **Posts:** Prediction summary, source attribution, deadline if present, link to archive

### Bot 2: Deadline reminder

- **Trigger:** GitHub Actions daily cron
- **Logic:** Scan all predictions, find `status: pending` with `deadline` within 30/7/1 days
- **State:** Tracks which reminders have been sent in `state/reminded.yaml` to prevent duplicates
- **Posts:** "X said Y would happen by Z — that's [N days] away" style reminder

The reminder bot is the higher-value feature. A new prediction is a data point. A reminder near a deadline is accountability.

### Seed data handling

Historical predictions are added with `skip_post: true`. The new-prediction bot ignores them. The reminder bot will still fire for them as deadlines approach — which is the correct behavior.

---

## Infrastructure

- **Storage:** GitHub repository (YAML files)
- **CI/Validation:** GitHub Actions — validates schema, categories, and filename format on every push
- **New post trigger:** GitHub Actions on push
- **Reminder trigger:** GitHub Actions daily cron
- **Hosting:** Static site generated from YAML files (tool TBD: likely a simple Python script to HTML, or Jekyll)
- **Secrets:** `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` in GitHub repository secrets

No backend database. No server. GitHub Actions is the compute layer.

---

## Phases

**Phase 1 — Data first**
Define final schema. Add 15-20 seed predictions with `skip_post: true`. Discover any missing fields before building automation.

**Phase 2 — Display**
Build the static site from the YAML files. Validate the schema works for real data. Publish the archive.

**Phase 3 — New prediction bot**
Implement `post_new.py` and the push trigger. Test with a live prediction.

**Phase 4 — Reminder bot**
Implement `reminders.py` and the daily cron. This is the most important feature.

**Phase 5 — Refinement**
Adjust post format, reminder cadence, and category taxonomy based on real usage.

---

## Success Criteria

- Adding a new prediction takes under two minutes
- Bot posts reliably on new entries (no false positives from edits/fixes)
- Reminder fires within 24 hours of 30/7/1-day thresholds
- Archive is publicly browsable and scannable

---

## Out of Scope

- User contributions or comments
- Backend database
- Automated prediction scraping
- Mobile app
- Social features
- Judging prediction accuracy

---

## Future Enhancements (Optional)

- RSS feed for new predictions
- Per-source and per-category statistics (categories.yaml makes this viable)
- Search on the static site
- Embeddable prediction cards
- Bluesky thread support for multi-part predictions
