# Final report — audit, semantic retrieval, bilingual evaluation

2026-11-15.

## 1. Audit conclusion

The earlier implementation was mostly sound but had never been executed end to end.
Three concrete problems were found and fixed in this session:

1. The backend image was stale — `sakti prepare --document-id` did not exist in the
   running container even though the code did.
2. The evaluation dataset was not mounted into the container, so the documented
   evaluation command failed with `FileNotFoundError`.
3. `hi_hi` and `en_hi` were blocked for lack of Hindi content, even though an official
   Hindi statute scan was already in `data/raw/official/`.

Everything else claimed by the previous session checked out when run: the retrieval
service, the API, the evaluation harness and 49 unit tests.

## 2. Retrieval architecture

`POST /api/v1/search` and `sakti query` → `RetrievalService.retrieve`

1. Validate request: non-empty query, top-k 1–20, cosine in [−1, 1], filter whitelist
   (`document_id`, `kind`, `language`, `jurisdiction`), jurisdiction/language values.
2. Tokenizer count of `query: <question>`; refuse above 512 tokens instead of truncating.
3. Load eligible documents (optionally restricted to `review_status: verified`).
4. Embed the whole query locally (`intfloat/multilingual-e5-small`, pinned revision,
   CPU, 384 dims).
5. Ann query `corpus_vector_v1`, cosine, `numCandidates = min(limit*20, 10000)`,
   `limit = max(100, top_k*20)`, 10 s `maxTimeMS`.
6. Convert `vectorSearchScore` back to cosine (`2v-1`), verify the stored vector
   contract, drop candidates under `min_score`.
7. Dedupe by parent, fetch parents in one batch, return child passage + parent context +
   citation (title, provision, pages, sha256, review status).

No application-side scan fallback exists; if no document qualifies, the response says so.

## 3. Results by language (real run)

| category | scored | R@5 | R@10 | P@5 | MRR@10 | nDCG@5 |
|---|---|---|---|---|---|---|
| en_en | 4 | 1.00 | 1.00 | 0.20 | 0.88 | 0.91 |
| hi_hi | 2 | 1.00 | 1.00 | 0.20 | 1.00 | 1.00 |
| hi_en | 4 | 0.50 | 0.50 | 0.10 | 0.38 | 0.41 |
| en_hi | 2 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| mixed | 4 | 0.75 | 1.00 | 0.15 | 0.48 | 0.53 |
| transliteration | 4 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| difficult | 6 | 0.67 | 0.83 | 0.13 | 0.69 | 0.67 |

Latency: 21–33 ms mean end-to-end after warm-up; first query 1.97 s (lazy model load).
No-answer abstention: 0/2 at 0.7.

## 4. Agent team actually used

No subagent capability was available in this environment, so the roles listed in the
master task (auditor, retrieval implementer, evaluator, reviewer) were executed
sequentially by one agent, with a separate review pass after implementation. This is a
limitation of execution, not of the work: the review produced independent findings
(F1–F7, E1–E6) rather than a restatement of the implementation.

## 5. Commands that were actually run, and their results

```bash
docker compose run --rm --no-deps -e PYTHONPATH=/app/src \
  -v ./backend/src:/app/src:ro -v ./backend/tests:/app/tests:ro \
  backend python -m unittest discover -s tests
# Ran 49 tests — OK (skipped=1)
# same command with -e RUN_MONGO_INTEGRATION=1 → Ran 65 tests — OK (live $vectorSearch)

docker compose build backend                      # rebuilt (old image lacked new flags)
docker compose run --rm backend sakti prepare --ocr --document-id 719552bf…
# Hindi Designs Act: 48 parents, 69 children, warning: compare OCR against images
docker compose run --rm backend sakti ingest
# 7 unchanged, 1 ingested (69 chunks), vector_index queryable

docker compose run --rm backend python -m ip_sakti.evaluation.bilingual
# 28 cases, 0 blocked → data/reports/bilingual-evaluation.json

docker compose up -d backend && curl -s localhost:8000/health/ready
# {"status":"ready","database":"sakti_sahayak"}

curl -s -X POST localhost:8000/api/v1/search -H 'content-type: application/json' \
  -d '{"query":"What are the absolute grounds for refusal of a trade mark?","top_k":2,"include_unverified":true,"min_score":-1}'
# mongodb_vector_ann; 0.872 Trade Marks Act s.9

docker compose exec -T mongodb mongosh … --eval '…'
# docs 8 | sections 652 | chunks 935 | embedded 935 | hi 1, en 7
```

## 6. Files changed in this session

- `compose.yaml` — mount `data/evaluation-bilingual.json` read-only.
- `data/evaluation-bilingual.json` — 2 blocked placeholders replaced by 4 grounded cases;
  history entry added.
- `data/catalog.json`, `data/sources-hindi.json`, `data/raw/official/719552bf….pdf` —
  Hindi source (authored earlier, ingested and used here).
- `.codex/` — `TASKS.md`, `PROJECT_STATE.md`, `build-log.md`, `tasks-in-progress/008`,
  `tasks-completed/015–019`, `evaluations/dataset.md`, `evaluations/retrieval-results.md`,
  `evaluations/failure-analysis.md`, `reviews/retrieval-review.md`,
  `reviews/bilingual-evaluation-review.md`, `reports/final-report.md`.
- Code from the previous session (`retrieval/search.py`, `storage/search.py`,
  `api/search.py`, `evaluation/bilingual.py`, tests) — verified, not rewritten.

## 7. Remaining problems, stated plainly

1. **Abstention does not work.** 0.7 admits everything; correct and wrong top-1 scores
   overlap. The system never says "not in the corpus".
2. **Transliteration fails (0/4).** Romanized Hindi does not reach the right provisions.
3. **English→Hindi fails (0/2)**, and Hindi→English is 0.50 — partly because the corpus
   now has both language versions, so queries pick their own language.
4. **Hindi sample is tiny** (2 cases per Hindi category, one document, OCR provenance
   unreviewed).
5. **All 8 sources are `needs_review`**, so default queries return nothing.
6. **Labels are provisional.** One judged parent per case; unjudged parents count as wrong.
7. **Two `difficult` cases had no hits** and are excluded from that category mean.
8. **Old generations are not cleaned up**; two PDFs still need OCR; no frontend work.

Nothing above is disguised as a pass. A partially verified implementation is reported as
such.
