# TODO

## Phase 1 — Data Foundation

- [ ] Create `categories.yaml` with initial vocabulary (`agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`)
- [ ] Create `template.yaml` with all fields, inline comments explaining each
- [ ] Create `predictions/` directory with a `.gitkeep`
- [ ] Create `state/` directory with a `.gitkeep`
- [ ] Add 15–20 seed predictions with `skip_post: true`
- [ ] Review seed data: check for missing fields, awkward categories, unclear deadlines
- [ ] Finalize schema (add/remove fields if the seed data revealed gaps)

## Phase 2 — Validation

- [ ] Write `scripts/validate.py`:
  - [ ] Required fields are present (`prediction_date`, `source_name`, `prediction_text`, `category`, `status`)
  - [ ] `category` is in `categories.yaml`
  - [ ] `status` is one of `pending`, `expired`, `notable`
  - [ ] `deadline` is a valid ISO date if present
  - [ ] `prediction_date` is a valid ISO date
  - [ ] `source_url` is a non-empty string if present
  - [ ] Filename matches `YYYY-MM-DD-*.yaml`
  - [ ] `skip_post` is a boolean if present
  - [ ] Exit non-zero on any validation failure with a clear error message
- [ ] Write `scripts/validate_test.py`:
  - [ ] Valid file passes all checks
  - [ ] Missing required field fails with correct error
  - [ ] Invalid category slug fails
  - [ ] Invalid status value fails
  - [ ] Malformed date in `deadline` fails
  - [ ] Malformed date in `prediction_date` fails
  - [ ] Badly named file fails
  - [ ] `skip_post` as a string instead of boolean fails
  - [ ] Empty `prediction_text` fails
- [ ] Add `.github/workflows/validate.yml` — runs `validate.py` on every push and PR

## Phase 3 — Data Entry Script

- [ ] Write `new_prediction.sh`:
  - [ ] Copies `template.yaml` to `predictions/` with today's date pre-filled
  - [ ] Slugifies a source name argument into the filename (e.g. `./new_prediction.sh "Sam Altman"` → `2026-04-13-sam-altman.yaml`)
  - [ ] Opens the file in `$EDITOR`
  - [ ] After editor exits, runs `validate.py` on the new file
  - [ ] Aborts with a clear message if validation fails
  - [ ] Stages and commits the file if validation passes
- [ ] Manual test: run the script, fill in a prediction, verify commit is created
- [ ] Manual test: save an invalid file, verify the script aborts and does not commit

## Phase 4 — Static Site

- [ ] Decide on generator (plain Python → HTML or Jekyll)
- [ ] Write `scripts/build_site.py` (or configure Jekyll):
  - [ ] Reads all `predictions/*.yaml`
  - [ ] Renders an index page sorted by `prediction_date` descending
  - [ ] Each row shows: date, source, prediction excerpt, category badge, deadline, status
  - [ ] Links each prediction to a detail page
  - [ ] Detail page shows all fields including full `prediction_text` and `notes`
  - [ ] Category filter on the index page
  - [ ] Status filter (`pending` / `expired` / `notable`)
- [ ] Write `scripts/build_site_test.py`:
  - [ ] Renders correctly with zero predictions (empty state)
  - [ ] Renders correctly with one prediction
  - [ ] Renders correctly with predictions missing optional fields (`deadline`, `notes`)
  - [ ] Category filter returns only matching predictions
  - [ ] Status filter returns only matching predictions
  - [ ] `notable` predictions display notes
  - [ ] `skip_post: true` predictions still appear on site
- [ ] Add `.github/workflows/deploy_site.yml` — builds and deploys to GitHub Pages on push to `main`
- [ ] Verify live site renders all seed predictions correctly

## Phase 5 — New Prediction Bot

- [ ] Create Bluesky bot account
- [ ] Add `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` to GitHub repository secrets
- [ ] Write `scripts/post_new.py`:
  - [ ] Accepts a YAML file path as argument
  - [ ] Formats a Bluesky post: source name, prediction excerpt (truncated cleanly to fit), deadline if present, link to archive
  - [ ] Skips files where `skip_post: true`
  - [ ] Posts via Bluesky API
  - [ ] Exits non-zero on API failure
- [ ] Write `scripts/post_new_test.py`:
  - [ ] Post is formatted correctly with all optional fields present
  - [ ] Post is formatted correctly when `deadline` is absent
  - [ ] Post is formatted correctly when `deadline_fuzzy` is present but `deadline` is absent
  - [ ] Post text does not exceed Bluesky character limit (300 chars)
  - [ ] Long `prediction_text` is truncated cleanly at a word boundary, not mid-word
  - [ ] File with `skip_post: true` produces no API call (mock the API)
  - [ ] API failure raises an exception and exits non-zero
- [ ] Add `.github/workflows/post_new.yml`:
  - [ ] Triggers on push to `main` affecting `predictions/*.yaml`
  - [ ] Diffs HEAD vs HEAD~1 to find newly added files only (not edits)
  - [ ] Calls `post_new.py` for each new file
  - [ ] Does not re-post files that were modified but already existed
- [ ] Integration test: add a real prediction (non-seed), verify Bluesky post appears
- [ ] Edge case test: fix a typo in an existing prediction, verify no duplicate post

## Phase 6 — Reminder Bot

- [ ] Write `scripts/reminders.py`:
  - [ ] Scans all `predictions/*.yaml`
  - [ ] Filters for `status: pending` with a parseable `deadline`
  - [ ] Fires reminders at 30, 7, and 1 days before deadline
  - [ ] Reads `state/reminded.yaml` to check which reminders have already been sent
  - [ ] Writes sent reminders back to `state/reminded.yaml`
  - [ ] Formats reminder post: "N days until [source]'s prediction: [excerpt]" + link
  - [ ] Does not post for `status: expired` or `status: notable`
  - [ ] Does not post for predictions with `skip_post: true`
- [ ] Write `scripts/reminders_test.py`:
  - [ ] Prediction at exactly 30 days out triggers reminder
  - [ ] Prediction at 29 days out does not trigger 30-day reminder
  - [ ] Prediction already in `state/reminded.yaml` for this threshold is not re-posted
  - [ ] `status: expired` prediction is skipped
  - [ ] `status: notable` prediction is skipped
  - [ ] `skip_post: true` prediction is skipped
  - [ ] Prediction with no `deadline` field is skipped
  - [ ] Prediction with unparseable `deadline` is skipped with a warning, not a crash
  - [ ] Multiple thresholds in one run (e.g. both 7-day and 1-day due today) each fire once
  - [ ] `state/reminded.yaml` is written correctly after a run
  - [ ] Dry-run mode prints what would be posted without calling the API
- [ ] Add `.github/workflows/reminders.yml` — runs daily at a fixed UTC time
- [ ] Add `state/reminded.yaml` with an empty initial structure, commit it
- [ ] Integration test: set a prediction deadline to tomorrow, run reminders manually, verify post

## Phase 7 — Hardening

- [ ] Add rate limit handling to both bot scripts (retry with backoff on 429)
- [ ] Add `scripts/check_state.py` — detects if `state/reminded.yaml` has drifted from `predictions/` (e.g. entries for deleted predictions)
- [ ] Test GitHub Actions workflows run cleanly on a fresh clone with no cached state
- [ ] Test the full new-prediction flow end-to-end: script → commit → Actions → Bluesky
- [ ] Test the full reminder flow end-to-end: prediction with near deadline → cron → Bluesky
- [ ] Add workflow failure notifications (GitHub Actions email or Bluesky DM to self)
- [ ] Document the `BLUESKY_APP_PASSWORD` rotation process in CLAUDE.md

## Ongoing

- [ ] After first 30 days of real use: review category taxonomy, rename slugs if needed
- [ ] After first deadline reminder fires: assess post format, adjust tone/length
- [ ] Periodic: update `status` of predictions past their deadline to `expired` or `notable`
