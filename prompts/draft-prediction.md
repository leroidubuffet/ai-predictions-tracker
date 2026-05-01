# Draft prediction from article

Use this prompt with any AI (Claude, ChatGPT, etc.) to generate a pre-filled prediction YAML from an article or interview. Paste the prompt, then paste the article text (or share the URL if the AI can browse).

---

## Prompt

Extract the main AI prediction from the article below and format it as a YAML file matching this schema exactly. Output only the YAML — no explanation, no markdown code fences.

**Schema:**
```
prediction_date: YYYY-MM-DD
source_name: ""
source_url: ""
prediction_text: |
  ...
deadline: ""
deadline_fuzzy: ""
category: ""
source_type: ""
conflict_of_interest: false
status: pending
notes: |
  ...
hashtags: ""
skip_post: false
importance: low
screenshot: ""
```

**Field rules:**
- `prediction_date`: the date the prediction was made (from the article/interview date)
- `source_name`: the person or organization making the prediction
- `source_url`: the URL of the article
- `prediction_text`: the actual claim, verbatim or very close paraphrase — must be the specific forecast, not background context. Include the full quote even if it is long; the bot truncates at a sentence boundary automatically when posting.
- `deadline`: ISO date (YYYY-MM-DD) only if a concrete year or date is stated; otherwise leave empty string
- `deadline_fuzzy`: human-readable timeframe if any is mentioned — e.g. `"within 5 years"`, `"by end of 2027"`, `"this decade"`; leave empty if none
- `category`: pick one from: `agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`
- `source_type`: pick one from: `researcher`, `practitioner`, `executive`, `investor`, `pundit`
  - `researcher` — academic or lab scientist
  - `practitioner` — engineer or scientist at an AI organisation
  - `executive` — CEO, C-suite, or senior leadership
  - `investor` — VC, fund manager, or financial stakeholder
  - `pundit` — journalist, commentator, or analyst without direct involvement
- `conflict_of_interest`: `true` if the source has a direct financial stake in the prediction being believed (e.g. a CEO promoting their product, a VC hyping their portfolio); `false` otherwise
- `status`: always `pending`
- `notes`: 2–3 sentences — who is this person, what context makes this prediction notable or worth tracking
- `hashtags`: leave as empty string `""` in almost all cases — the bot automatically uses `#AIPredictions` plus the category-specific tag. Only set this field if you need to override the defaults entirely (e.g. a prediction that spans multiple categories or needs a one-off tag). If you do override, include `#AIPredictions` manually since the field replaces everything.
- `skip_post`: always `false`
- `importance`: `high` if the prediction is about existential risk, AGI arrival, or large-scale societal impact; `low` for everything else. Controls how often elapsed-time reminders fire (high = every 6 months, low = every 12 months). Only relevant when `deadline` is empty.
- `screenshot`: leave as empty string — you cannot attach a file

If the article contains multiple predictions, pick the most specific and falsifiable one.

**Article:**
[paste article text or URL here]
