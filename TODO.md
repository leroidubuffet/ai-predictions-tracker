# TODO

## Phase 1 — Data Foundation ✓

- [x] Create `categories.yaml` with initial vocabulary (`agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`)
- [x] Create `template.yaml` with all fields, inline comments explaining each
- [x] Create `predictions/` directory with a `.gitkeep`
- [x] Create `state/` directory with a `.gitkeep`
- [x] Add 15–20 seed predictions with `skip_post: true` (17 added)
- [x] Review seed data: check for missing fields, awkward categories, unclear deadlines
- [x] Finalize schema (add/remove fields if the seed data revealed gaps)

## Phase 2 — Validation ✓

- [x] Write `scripts/validate.py`:
  - [x] Required fields are present (`prediction_date`, `source_name`, `prediction_text`, `category`, `status`)
  - [x] `category` is in `categories.yaml`
  - [x] `status` is one of `pending`, `expired`, `notable`
  - [x] `deadline` is a valid ISO date if present
  - [x] `prediction_date` is a valid ISO date
  - [x] Filename matches `YYYY-MM-DD-*.yaml`
  - [x] `skip_post` is a boolean if present
  - [x] Exit non-zero on any validation failure with a clear error message
- [x] Write `scripts/validate_test.py` (28 tests, all passing):
  - [x] Valid file passes all checks
  - [x] Missing required field fails with correct error
  - [x] Invalid category slug fails
  - [x] Invalid status value fails
  - [x] Malformed date in `deadline` fails
  - [x] Malformed date in `prediction_date` fails
  - [x] Badly named file fails
  - [x] `skip_post` as a string instead of boolean fails
  - [x] Empty `prediction_text` fails
- [x] Add `.github/workflows/validate.yml` — runs `validate.py` on every push and PR

## Phase 3 — Data Entry Script ✓

- [x] Write `new_prediction.sh`:
  - [x] Copies `template.yaml` to `predictions/` with today's date pre-filled
  - [x] Slugifies a source name argument into the filename
  - [x] Opens the file in `$EDITOR`
  - [x] After editor exits, runs `validate.py` on the new file
  - [x] Aborts with a clear message if validation fails
  - [x] Stages and commits the file if validation passes
- [ ] Manual test: run the script, fill in a prediction, verify commit is created
- [ ] Manual test: save an invalid file, verify the script aborts and does not commit

## Phase 4 — New Prediction Bot

- [ ] Create Bluesky bot account
- [ ] Add `BLUESKY_HANDLE` and `BLUESKY_APP_PASSWORD` to GitHub repository secrets
- [ ] Write `scripts/post_new.py`:
  - [ ] Accepts a YAML file path as argument
  - [ ] Formats a Bluesky post: source name, prediction excerpt (truncated cleanly at word boundary to fit 300 chars), deadline if present
  - [ ] Skips files where `skip_post: true`
  - [ ] Posts via Bluesky API (atproto library)
  - [ ] Exits non-zero on API failure
- [ ] Write `scripts/post_new_test.py`:
  - [ ] Post is formatted correctly with all optional fields present
  - [ ] Post is formatted correctly when `deadline` is absent
  - [ ] Post is formatted correctly when `deadline_fuzzy` is present but `deadline` is absent
  - [ ] Post text does not exceed 300 characters
  - [ ] Long `prediction_text` is truncated at a word boundary, not mid-word
  - [ ] File with `skip_post: true` produces no API call (mock the API)
  - [ ] API failure raises an exception and exits non-zero
- [ ] Add `.github/workflows/post_new.yml`:
  - [ ] Triggers on push to `main` affecting `predictions/*.yaml`
  - [ ] Diffs HEAD vs HEAD~1 to find newly added files only (not edits)
  - [ ] Calls `post_new.py` for each new file
  - [ ] Does not re-post files that were modified but already existed
- [ ] Integration test: add a real prediction, verify Bluesky post appears
- [ ] Edge case test: fix a typo in an existing prediction, verify no duplicate post

## Phase 5 — Reminder Bot

- [ ] Write `scripts/reminders.py`:
  - [ ] Scans all `predictions/*.yaml`
  - [ ] Filters for `status: pending` with a parseable `deadline`
  - [ ] Fires reminders at 30, 7, and 1 days before deadline
  - [ ] Reads `state/reminded.yaml` to check which reminders have already been sent
  - [ ] Writes sent reminders back to `state/reminded.yaml`
  - [ ] Formats post: "N days until [source]'s prediction: [excerpt]"
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
  - [ ] Multiple thresholds in one run each fire independently
  - [ ] `state/reminded.yaml` is written correctly after a run
  - [ ] Dry-run mode prints what would be posted without calling the API
- [ ] Add `.github/workflows/reminders.yml` — runs daily at a fixed UTC time
- [ ] Integration test: set a prediction deadline to tomorrow, run reminders manually, verify post

## Phase 6 — Hardening

- [ ] Add rate limit handling to both bot scripts (retry with backoff on 429)
- [ ] Add `scripts/check_state.py` — detects if `state/reminded.yaml` has drifted from `predictions/`
- [ ] Test GitHub Actions workflows run cleanly on a fresh clone with no cached state
- [ ] Test the full new-prediction flow end-to-end: script → commit → Actions → Bluesky
- [ ] Test the full reminder flow end-to-end: prediction with near deadline → cron → Bluesky
- [ ] Document the `BLUESKY_APP_PASSWORD` rotation process in CLAUDE.md

## Ongoing

- [ ] After first 30 days of real use: review category taxonomy, rename slugs if needed
- [ ] After first deadline reminder fires: assess post format, adjust tone/length
- [ ] Periodic: update `status` of predictions past their deadline to `expired` or `notable`
