# User Manual

## Daily workflow

### Adding a prediction

```bash
./new_prediction.sh "Source Name"
```

This opens a pre-filled YAML file in your `$EDITOR`. Fill in the fields, save, and exit. The script validates the file and commits it automatically. If validation fails, it prints the errors and leaves the file for you to fix — no commit is made.

The new prediction is posted to Bluesky automatically when the commit is pushed.

**Example:**
```bash
./new_prediction.sh "Yann LeCun"
# opens predictions/2026-04-13-yann-lecun.yaml in your editor
```

### Running scripts manually

Always use the project's virtual environment:

```bash
.venv/bin/python scripts/reminders.py --dry-run   # preview upcoming reminders
.venv/bin/python scripts/validate.py               # validate all predictions
.venv/bin/python scripts/check_state.py            # check for state drift
```

### Manually posting a prediction

The bot posts automatically on push, but you can trigger a post manually two ways.

**Via GitHub Actions** (recommended — uses stored secrets, no local setup):
```bash
gh workflow run post_new.yml --field file="predictions/2024-03-15-sam-altman.yaml"
```

**Locally** (requires env vars):
```bash
BLUESKY_HANDLE=yourhandle.bsky.social \
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx \
.venv/bin/python scripts/post_new.py predictions/2024-03-15-sam-altman.yaml
```

Both methods respect `skip_post: true` — the file will be silently skipped if it's set. Make sure it's `false` before triggering.

---

## Prediction file format

Files live in `predictions/` and follow the naming pattern `YYYY-MM-DD-source-slug.yaml`.

```yaml
prediction_date: 2026-04-13        # required — when the prediction was made
source_name: Sam Altman            # required — person or organization
source_url: https://...            # optional but encouraged — link to original
prediction_text: |                 # required — verbatim or close paraphrase
  The full prediction text goes here.
  Multi-line is fine.
deadline: 2027-12-31               # optional — ISO date
deadline_fuzzy: "by end of 2027"   # optional — human-readable form
category: agi                      # required — must be in categories.yaml
source_type: executive             # required — researcher | practitioner | executive | investor | pundit
conflict_of_interest: false        # required — true if source has financial stake in the prediction being believed
status: pending                    # required — pending | expired | notable
notes: |                           # optional — context, outcome notes
  Any extra context.
hashtags: ""                       # optional — overrides default #AIPredictions, space-separated
skip_post: false                   # required — false: post to Bluesky on commit; true: archive only, never post
importance: low                    # optional — high | low (only used when no deadline is set)
post_excerpt: ""                   # optional — short version for Bluesky posts; omit to use
                                   # prediction_text (auto-truncated at sentence boundary if needed)
screenshot: ""                     # optional — path relative to repo root, e.g.
                                   # predictions/assets/2026-04-26-altman-tweet.png
```

### Importance (no-deadline predictions)

For predictions without a deadline, the reminder bot fires periodically based on elapsed time since `prediction_date`. The `importance` field controls the interval:

| Value | Reminder interval |
|---|---|
| `low` (default) | Every 1 year (365 days) |
| `high` | Every 6 months (183 days) |

Posts are formatted as *"6 months ago, [name] predicted: …"* and catch up on missed intervals — if the bot was offline for a stretch, all un-sent intervals fire on the next run.

### Screenshots

To archive a screenshot of the original source (useful when the source may be deleted):

1. Save the image file under `predictions/assets/` using a descriptive name matching the prediction filename.
2. Set `screenshot: predictions/assets/your-file.png` in the YAML.

When the prediction is posted to Bluesky, the screenshot is attached as an image. If the upload fails, the post falls back to attaching the `source_url` as a link card instead. Supported formats: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`.

### Status values

| Value | Meaning |
|---|---|
| `pending` | Deadline hasn't passed, no update |
| `expired` | Deadline passed, nothing notable happened |
| `notable` | Something worth recording — add context in `notes` |

Status is never set automatically. Update it manually as deadlines pass.

### Categories

Valid values are defined in `categories.yaml`:

| Slug | Use for |
|---|---|
| `agi` | AGI arrival or definition predictions |
| `capabilities` | Specific model or system capability milestones |
| `jobs` | Employment and labor market impact |
| `regulation` | Laws, policy, government action |
| `safety` | Existential risk, alignment outcomes |
| `timelines` | General timeline predictions |
| `hardware` | Chips, compute, infrastructure |
| `alignment` | Technical alignment research progress |

To add a new category, add the slug to `categories.yaml` first — validation will reject any file that uses an undeclared slug.

---

## skip_post: archive vs. broadcast

Every prediction file is either **broadcast** (`skip_post: false`) or **archive-only** (`skip_post: true`).

**Broadcast** (`false`, the default): when you push the file, the new-prediction bot posts it to Bluesky. The reminder bot will also post reminders and elapsed-time posts as time passes. This is what you want for predictions you're adding in real time.

**Archive-only** (`true`): the file lives in the repo as a permanent record but both bots ignore it completely — no initial post, no reminders, nothing. This is what you want when:
- You're backfilling historical predictions (adding a dozen old claims at once — you don't want to flood the feed with ancient news)
- You want to record something for personal reference without broadcasting it

The archive still has value: the data is versioned, searchable, and available for future use. It just doesn't go to Bluesky.

---

## Bots

### New prediction bot

Triggers automatically on every push to `main` that adds a file to `predictions/`. It diffs `HEAD~1..HEAD` to find newly added files — editing an existing prediction does not re-post it. Skips `skip_post: true`.

If the prediction has a `screenshot` field pointing to a file in `predictions/assets/`, the image is attached to the post. Otherwise the `source_url` is attached as a link card.

Post format:
```
🔮 New prediction registered 🔮

By: Sam Altman
Date: December 2024

"My guess is we will hit AGI sooner than most people think..."

Deadline: during 2025

#AIPredictions
```

If `prediction_text` is too long to fit in 300 characters, it is truncated automatically — first at a sentence boundary (`.`, `!`, `?`) if one exists within budget, then at a word boundary. Store the full text in the YAML; the bot handles the rest.

For long or multi-sentence quotes where auto-truncation produces an awkward result, set `post_excerpt` to a curated one-sentence version. The full quote stays in `prediction_text` as the archival record; `post_excerpt` is used only for posting.

### Reminder bot

Runs daily at 09:00 UTC via GitHub Actions. Skips `skip_post: true` and non-`pending` predictions. State is tracked in `state/reminded.yaml` and committed back after each run.

**Predictions with a deadline** fire reminders at **30, 7, and 1 days** before the deadline. Multi-year predictions also get annual milestone reminders (1 year out, 2 years out, etc.). When the deadline passes, a one-time expired post fires.

```
30 days left on Sam Altman's prediction (Dec 31, 2025):

"My guess is we will hit AGI sooner than most people think..."

#AIPredictions
```

On the calendar anniversary of any deadline-based prediction, an anniversary post fires:

```
1 year ago, Sam Altman predicted:

"My guess is we will hit AGI sooner than most people think..."

#AIPredictions
```

**Predictions without a deadline** get elapsed-time reminders based on `importance` (every 6 months for `high`, every year for `low`). All un-sent intervals are caught up on each run.

```
1 year ago, Sam Altman predicted:

"i am switching to polyphasic sleep because GPT-5.5 in codex is so good…"

#AIPredictions
```

To preview what would fire today without posting anything:

```bash
.venv/bin/python scripts/reminders.py --dry-run
```

---

## Setup (one-time)

### 1. Python environment

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 2. Bluesky bot account

1. Create a new account at [bsky.app](https://bsky.app)
2. Go to **Settings → Privacy and Security → App Passwords**
3. Generate an app password (do not use your main account password)

### 3. GitHub secrets

In the repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `BLUESKY_HANDLE` | Your bot's handle, e.g. `aipredictions.bsky.social` |
| `BLUESKY_APP_PASSWORD` | The app password from step 2 |

### 4. Verify the setup

Add a test prediction with `skip_post: false`, push it, and confirm the post appears on Bluesky. Then delete or set `skip_post: true` if it was a test.

---

## Rotating the app password

1. Go to **Settings → Privacy and Security → App Passwords** on Bluesky
2. Delete the old app password
3. Generate a new one
4. Update the `BLUESKY_APP_PASSWORD` secret in GitHub

The old password is invalidated immediately. Update the secret before the next scheduled bot run.

---

## Troubleshooting

**`command not found: python`**
Use `.venv/bin/python` instead of `python`. The system Python may not be in PATH or may be Python 2.

**Validation fails on a new file**
The script prints the specific errors. Common causes: wrong `category` slug (check `categories.yaml`), `deadline` not in `YYYY-MM-DD` format, `skip_post` set to a string instead of `true`/`false`.

**Bot didn't post after a push**
Check the Actions tab on GitHub. Common causes: secrets not set, the file already existed (edit rather than add), or `skip_post: true`.

**Reminder fired twice**
Shouldn't happen — check `state/reminded.yaml` for the entry. If it's missing, the state commit may have failed. Check the Actions log for the reminders workflow.

**State drift warning from `check_state.py`**
A prediction file was deleted but its entry remains in `state/reminded.yaml`. Edit `state/reminded.yaml` manually and remove the orphaned key.
