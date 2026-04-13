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
status: pending
notes: |
  ...
skip_post: false
```

**Field rules:**
- `prediction_date`: the date the prediction was made (from the article/interview date)
- `source_name`: the person or organization making the prediction
- `source_url`: the URL of the article
- `prediction_text`: the actual claim, verbatim or very close paraphrase — must be the specific forecast, not background context
- `deadline`: ISO date (YYYY-MM-DD) only if a concrete year or date is stated; otherwise leave empty string
- `deadline_fuzzy`: human-readable timeframe if any is mentioned — e.g. `"within 5 years"`, `"by end of 2027"`, `"this decade"`; leave empty if none
- `category`: pick one from: `agi`, `capabilities`, `jobs`, `regulation`, `safety`, `timelines`, `hardware`, `alignment`
- `status`: always `pending`
- `notes`: 2–3 sentences — who is this person, what context makes this prediction notable or worth tracking
- `skip_post`: always `false`

If the article contains multiple predictions, pick the most specific and falsifiable one.

**Article:**
[paste article text or URL here]
