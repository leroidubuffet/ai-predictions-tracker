# Hashtag Strategy

## Approach

Three layers:

1. **Campaign tag** — one ownable tag on every post. Builds a searchable archive over time. Zero reach at first, but compounds as the account grows. Ours: `#AIPredictions`.
2. **Topic tags** — broad tags with existing audiences. This is where discovery happens. Use 2–3 per post, chosen for the content of that prediction.
3. **Moment tags** — opportunistic tags tied to news cycles. Not used here since posts are automated.

The campaign tag goes on every post. Topic tags vary by category.

---

## Proposed tags by category

These are candidates. **Validate each against actual Bluesky traffic before committing** — check feed activity and whether real engaged accounts use them.

| Category | Proposed tags | Notes |
|---|---|---|
| `agi/agi` | `#AGI` `#ASI` | Core topic for this project |
| `capabilities` | `#AI` `#MachineLearning` | Broad but likely the highest-traffic options for model/benchmark news |
| `jobs` | `#AIJobs` |  |
| `regulation` | `#AIPolicy` `#AIRegulation` | Policy crowd is active on Bluesky |
| `safety` | `#AISafety` `#AIRisk` |  |
| `hardware` | `#AI` `#Semiconductors` | `#Semiconductors` is niche but precise; `#AI` is broad fallback |
| `alignment` | `#AISafety` `#AIAlignment` | Check if `#AIAlignment` has traction or if `#AISafety` covers it |

---

## Validation checklist

For each candidate tag, check on Bluesky:

- [ ] How many posts in the last 7 days?
- [ ] Are they from real accounts or noise?
- [ ] Does a curated feed exist for this tag?
- [ ] What do high-follower AI accounts actually use?

---

## Implementation

Once tags are validated, add a `default_hashtags` field to each category entry in `categories.yaml`. Both posting scripts will fall back to the category defaults when no per-prediction `hashtags` override is set.

The per-prediction `hashtags` field remains available for cases where the category defaults don't fit.
