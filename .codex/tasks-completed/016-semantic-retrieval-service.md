# 016 Repair defects and reusable semantic retrieval

Request: keep existing working behaviour, repair real defects, expose one retrieval
service used by CLI and API with true cosine scores and configurable threshold.

## Implementation

- `storage/search.py` — `SearchRepository`: eligible-document selection, contract/index
  check, bounded ANN candidate query (`numCandidates = min(limit*20, 10000)`,
  `maxTimeMS`), batch parent fetch.
- `retrieval/search.py` — `RetrievalService.retrieve`: request validation (query,
  top-k 1–20, score −1…1, filter whitelist, jurisdiction/language values), 512-token
  refusal via tokenizer count, query embedding, `mongo_cosine_score` (`2v-1`), parent
  dedupe, integrity checks on every candidate, structured `timings`/`note`.
- No application-side full-scan fallback; an empty eligible set returns a `reason`.
- `sakti query` gained `--min-score`, `--document-id`, `--kind`, `--language`, `--json`.
- `POST /api/v1/search` added with `extra="forbid"` models and a non-blocking lock.

## Checks actually run

- Unit suite covers validation, score mapping, dedupe, contract failures and the API
  schema: 49 tests, 48 pass, 1 opt-in skip.
- Full suite with `RUN_MONGO_INTEGRATION=1`: 65 tests, all pass against the live
  database (real `$vectorSearch`), 2.3 s.
- Live API returned `search_strategy: mongodb_vector_ann` and a real cosine 0.872 for
  Trade Marks s.9.

## Limitations

- Concurrency 503 path and `kind`/`language` request filters were not exercised end to
  end (only validated statically) — recorded in `reviews/retrieval-review.md` F6.
- `candidate_limit_reached` is true on this corpus even for `top_k=2` because of the
  100-candidate floor.
- Old-generation children are still not deleted.

Next: 017.
