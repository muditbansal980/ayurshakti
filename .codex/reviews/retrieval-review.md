# Independent review: semantic retrieval

Date: 2026-11-15. Reviewer: implementation session (separate review pass after coding).
Scope: `storage/search.py`, `retrieval/search.py`, `api/search.py`, `api/app.py`, `cli.py`,
`storage/ingest.py`, `storage/indexes.py`, `embeddings/local.py`.

## Verdict

The retrieval path is sound and runs against real MongoDB `$vectorSearch`. It is not a
rank-fusion rename: candidates come from ANN, scores are true cosine, and parents are
fetched in one batch. Four defects remain, none of which invalidate the stored corpus.
Two of them (threshold calibration, transliteration recall) are capability limits that
must be reported, not papered over.

## What was checked, and how

| Claim | Evidence |
|---|---|
| Tests pass | default run: 49 tests, 48 pass, 1 opt-in Mongo skip. With `RUN_MONGO_INTEGRATION=1`: 65 tests, all pass against the live database |
| ANN index usable | `vector_index: queryable` after ingest; API returned `search_strategy: mongodb_vector_ann` |
| Scores are cosine | `mongo_cosine_score` maps `vectorSearchScore` via `2v-1`; result `0.872` for Trade Marks s.9 |
| Full contract enforced | Every candidate child is rejected unless model/revision/384 dims/generation/parent/jurisdiction match |
| No silent fallback | Empty eligible set returns a `reason`, never an application-side scan |
| No unbounded query | Tokenizer count checked; >512 tokens raises instead of truncating |
| Parent dedupe + batch | `selected` keyed by `parent_id`; `parents()` fetches once |

Runtime: 8 documents (7 en, 1 hi), 652 parents, 935 children, 935 with embeddings.

## Findings

### F1 — Default `min_score=0.7` filters nothing (medium)

Measured top-1 cosine across the 28-case set:

- cases with a gold parent in top 10: 0.830–0.914 (mean 0.874)
- cases with no gold parent in top 10: 0.802–0.891 (mean 0.846)
- out-of-scope probes: 0.772 and 0.785, both returned 10 hits

The distributions overlap completely, so a fixed absolute cosine cannot separate
answerable from unanswerable. The `note` field already calls 0.7 an uncalibrated
heuristic, and evaluation ranks with `min_score=-1` separately, so this is honest.
It is still a usability trap: callers reading "min_score 0.7" will believe results
were vetted. Recommendation: keep the field, but do not present it as a confidence
gate; a later change should abstain on top-1 margin or a calibrated per-model cut.

### F2 — Romanized Hindi queries miss (4/4) (capability limit)

All four transliteration cases returned their top hits inside the Hindi Designs Act
(Devanagari), not the expected English statutes, with scores 0.796–0.839. The model
does not map Latin transliteration onto the right legal provision. Recorded as a
failure category, not averaged into overall quality.

### F3 — English→Hindi cross-lingual retrieval misses (0/2) (capability limit)

English queries about a topic present in both language versions retrieve the English
statute (top-1 in both cases). With one Hindi document among eight, the Hindi sibling
never enters the top 10. Expected for a 118M-parameter model on a lopsided corpus.

### F4 — Cold start dominates single-shot CLI latency (low)

Measured 8.0 s and 11.5 s for `sakti query` runs, of which `validation_ms` (tokenizer
load) was 3.5–5.7 s and `embedding_ms` 4.5–5.8 s. Steady-state retrieval is 21–33 ms.
Each CLI invocation reloads both; the API pays this once at first request, not per
request. Document as a known cost, not a defect to hide.

### F5 — `candidate_limit_reached` is always true on this corpus (low, cosmetic)

`limit = max(100, top_k*20)` and a corpus of 935 children means ANN returns exactly 100
candidates, so the flag is true even for `top_k=2`. The flag means "ANN cap hit", not
"results truncated"; the response note covers this, but the name invites misreading.

### F6 — Untested paths (explicit gaps)

- The non-blocking retrieval lock returning HTTP 503 was not exercised with concurrent
  requests; only the happy path was called.
- `kind` / `language` filters were validated statically and by the Hindi documents'
  metadata, but no filtered request was run end to end.
- Old-generation children are still not cleaned up after re-ingest (known limitation,
  unchanged from the earlier audit).

### F7 — Default queries return empty until review (expected, blocking for product)

All 8 documents remain `review_status: needs_review`. CLI/API therefore require
`--include-unverified` / `include_unverified: true`. This is correct behaviour, not a
bug, but production use is blocked on human source review.
