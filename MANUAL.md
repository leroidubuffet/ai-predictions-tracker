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
status: pending                    # required — pending | expired | notable
notes: |                           # optional — context, outcome notes
  Any extra context.
skip_post: false                   # required — true for historical/seed data
```

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

## Seed / historical data

For predictions made in the past that you don't want posted to Bluesky:

```yaml
skip_post: true
```

The new-prediction bot skips these entirely. The reminder bot still fires for them as their deadlines approach — which is the intended behaviour.

---

## Bots

### New prediction bot

Triggers automatically on every push to `main` that adds a file to `predictions/`. It diffs `HEAD~1..HEAD` to find newly added files — editing an existing prediction does not re-post it.

Posts in this format:
```
Sam Altman (2024):
"My guess is we will hit AGI sooner than most people think..."

Deadline: during 2025
```

### Reminder bot

Runs daily at 09:00 UTC via GitHub Actions. Scans all `status: pending` predictions with a `deadline` and fires reminders at **30, 7, and 1 days** before the deadline.

Each reminder is posted once — state is tracked in `state/reminded.yaml` and committed back to the repo automatically after each run.

Post format:
```
30 days until Sam Altman's prediction deadline (Dec 31, 2025):

"My guess is we will hit AGI sooner than most people think..."
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
